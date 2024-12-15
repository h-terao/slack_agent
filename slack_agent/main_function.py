from typing import Callable

from slack_bolt.app import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from slack_agent import events
from slack_agent.functions import get_functions


def make_main_function(
    model_name: str,
    system_instruction: str,
    google_api_token: str,
    slack_bot_token: str,
    slack_app_token: str,
) -> Callable[[], None]:
    app = App(token=slack_bot_token)

    # Register events and commands.
    app.event("app_mention")(
        events.make_app_mention_event(
            model_name=model_name,
            google_api_token=google_api_token,
            slack_bot_token=slack_bot_token,
            system_instruction=system_instruction,
            tools=get_functions(),
        )
    )

    def main():
        handler = SocketModeHandler(app, app_token=slack_app_token)
        handler.start()

    return main
