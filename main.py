import os
import dotenv
from slack_agent import make_main_function

dotenv.load_dotenv()

# Collect the environment variables.
google_api_token = os.environ["GOOGLE_API_TOKEN"]
slack_bot_token = os.environ["SLACK_BOT_TOKEN"]
slack_app_token = os.environ["SLACK_APP_TOKEN"]

# Parameters.
model_name = "gemini-2.0-flash-exp"
system_instruction = """
あなたはSlack上でユーザとコミュニケーションをとっています。
あなたはユーザからメンションされたとき、以下の指示に従いながら、適切な返答をする必要があります。
- ユーザからのメッセージは必ず @<あなたのID> から始まります。@<あなたのID> はあなた自身を指しているため、返答にこのメンションを含む必要はありません。
- ユーザからの質問に対しては、できるだけ正確な返答をしてください。
- 曖昧な質問に対しては、ユーザに質問を返すことで明確にしてください。ただし、質問を返す際にはどこまでは分かっていて何が分からないのか、どのような情報が必要なのかなど、ユーザに対して質問を返した理由を添えるようにしてください。
"""

if __name__ == "__main__":
    main = make_main_function(
        model_name=model_name,
        system_instruction=system_instruction,
        google_api_token=google_api_token,
        slack_bot_token=slack_bot_token,
        slack_app_token=slack_app_token,
    )

    main()
