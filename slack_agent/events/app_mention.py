import json
import requests
import io
import time

from google import generativeai as genai
from google.api_core.exceptions import PermissionDenied

from slack_agent.functions import call_function


SUPPORTED_MIME_TYPES = [
    # https://ai.google.dev/gemini-api/docs/vision?hl=ja&lang=python
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/heic",
    "image/heif",
    "video/mp4",
    "video/mpeg",
    "video/avi",
    "video/x-flv",
    "video/mpg",
    "video/webm",
    "video/wmv",
    "video/3gpp",
    # https://ai.google.dev/gemini-api/docs/audio?hl=ja&lang=python
    "audio/wav",
    "audio/mp3",
    "audio/aiff",
    "audio/aac",
    "audio/ogg",
    "audio/flac",
    # https://ai.google.dev/gemini-api/docs/document-processing?hl=ja&lang=python
    "application/pdf",
    "application/x-javascript",
    "text/javascript",
    "application/x-python",
    "text/x-python",
    "text/plain",
    "text/html",
    "text/css",
    "text/md",
    "text/csv",
    "text/xml",
    "text/rtf",
]


def make_app_mention_event(
    model_name: str,
    google_api_token: str,
    slack_bot_token: str,
    system_instruction: str,
    tools: list | None = None,
):
    genai.configure(api_key=google_api_token)

    model = genai.GenerativeModel(
        model_name=model_name,
        tools=tools,
        system_instruction=system_instruction,
    )

    file_upload_dict: dict[str, str] = {}
    for file in genai.list_files(page_size=100):
        # Fetch the last 100 files.
        file_upload_dict[file.display_name] = file.name

    def get_function_call_history(file_url: str) -> list:
        function_call_history = []

        request_response = requests.get(file_url, headers={"Authorization": f"Bearer {slack_bot_token}"})
        for message in json.loads(request_response.content):
            parts = []
            for elem in message["parts"]:
                match elem["part_type"]:
                    case "function_call":
                        part = genai.protos.Part(
                            function_call=genai.protos.FunctionCall(
                                name=elem["name"],
                                args=elem["args"],
                            )
                        )
                    case "function_response":
                        part = genai.protos.Part(
                            function_response=genai.protos.FunctionResponse(
                                name=elem["name"],
                                response={"result": elem["value"]},
                            )
                        )
                    case _:
                        raise ValueError(f"Unknown part type: {elem['part_type']}")
                parts.append(part)
            function_call_history.append({"role": message["role"], "parts": parts})

        return function_call_history

    def get_file_part(file_url, file_id, mimetype):
        if mimetype not in SUPPORTED_MIME_TYPES:
            return None

        file = None
        if file_id in file_upload_dict:
            # If file is recently uploaded, Google would have it.
            # Then, we can skip the file upload process.
            name = file_upload_dict[file_id]
            try:
                file = genai.get_file(name)
            except PermissionDenied:
                del file_upload_dict[file_id]  # This file would be deleted.

        if file is None:
            # Upload file.
            request_response = requests.get(file_url, headers={"Authorization": f"Bearer {slack_bot_token}"})
            file_bytes = io.BytesIO(request_response.content)
            file = genai.upload_file(file_bytes, display_name=file_id, mime_type=mimetype)

        if "video" in mimetype:
            while file.state.name == "PROCESSING":
                time.sleep(5)
                file = genai.get_file(file.name)

        file_upload_dict[file_id] = file.name
        return file

    def get_thread_messages(client, channel, thread_ts) -> tuple:
        thread_messages = []

        response = client.conversations_replies(channel=channel, ts=thread_ts)
        for slack_message in response["messages"]:
            role = "model" if "bot_profile" in slack_message else "user"

            parts = []
            if "files" in slack_message:
                for file in slack_message["files"]:
                    if file["name"] == "function_call.json":
                        # Add function calling results to history.
                        thread_messages += get_function_call_history(file_url=file["url_private_download"])
                    else:
                        if file_part := get_file_part(
                            file_url=file["url_private_download"],
                            file_id=file["id"],
                            mimetype=file["mimetype"],
                        ):
                            parts.append(file_part)

            if "text" in slack_message:
                parts.append(slack_message["text"])

            thread_messages.append({"role": role, "parts": parts})

        *history, message = thread_messages
        return message, history

    def event_fun(ack, say, body, client):
        ack()

        event = body["event"]
        channel = event["channel"]
        event_ts = event["ts"]

        history = None
        if "thread_ts" in event:
            message, history = get_thread_messages(client, channel, event["thread_ts"])
        else:
            # No thread.
            message = [event["text"]]
            for file in event.get("files", []):
                if file_part := get_file_part(
                    file_url=file["url_private_download"],
                    file_id=file["id"],
                    mimetype=file["mimetype"],
                ):
                    message.append(file_part)

        chat = model.start_chat(history=history)
        response = chat.send_message(message)

        function_call_history = []
        while funtion_call_parts := [part for part in response.parts if part.function_call]:
            function_responses = {}
            for function_call_part in funtion_call_parts:
                function_name = function_call_part.function_call.name
                function_arguments = function_call_part.function_call.args

                function_responses[function_name] = call_function(function_name, **function_arguments)
                function_call_history.append(
                    {
                        "part_type": "function_call",
                        "name": function_name,
                        "args": dict(function_arguments),
                    }
                )

            response_parts = []
            for function_name, function_response in function_responses.items():
                response_parts.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_name,
                            response={"result": function_response},
                        )
                    )
                )

                function_call_history.append(
                    {
                        "part_type": "function_response",
                        "name": function_name,
                        "response": function_response,
                    }
                )

            response = chat.send_message(response_parts)

        message = response.candidates[0].content.parts[0].text
        if function_call_history:
            client.files_upload_v2(
                filename="function_call.json",
                content=json.dumps(function_call_history, ensure_ascii=False, indent=2),
                channel=channel,
                initial_comment=message,
                thread_ts=event_ts,
            )
        else:
            say(message, channel=channel, thread_ts=event_ts)

    return event_fun
