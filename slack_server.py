import os
import slack_sdk as slack
from flask import Flask
from flask import make_response
from slackeventsapi import SlackEventAdapter
from waitress import serve
import threading
import autogen
from langchain_community.tools.gmail.utils import (
    build_resource_service,
    get_gmail_credentials,
)
from langchain_community.agent_toolkits import GmailToolkit
from langchain_openai import ChatOpenAI
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from dotenv import load_dotenv
from langchain_community.tools import DuckDuckGoSearchRun
from custom_functions.calender_functions import CalendarToolkit
from datetime import datetime
import pytz

load_dotenv(override=True)
app = Flask(__name__)

eventAdapter = SlackEventAdapter(
    os.environ["SLACK_SIGNING_SECRET"], "/slack/events", app
)

client = slack.WebClient(token=os.environ["SLACK_BOT_TOKEN"])

bot = client.api_call("auth.test")["user_id"]


@eventAdapter.on("message")
def onMessage(message):
    event = message.get("event", {})
    # Check if the bot's user ID is mentioned in the text
    if bot in event.get("text", ""):
        # Respond immediately with 200 OK
        response = make_response("", 200)
        # Start a new thread for processing the message
        thread = threading.Thread(target=handle_message_in_thread, args=(message,))
        thread.start()
        return response
    else:
        # If the bot is not mentioned, just respond with 200 OK without processing
        return make_response("", 200)


def handle_message_in_thread(message):
    print("for me the bot")
    event = message.get("event", {})
    channel = event.get("channel")
    user = event.get("user")
    text = event.get("text")
    ts = event.get("ts")
    updatedText = text.replace("<@" + bot + ">", "Donna")
    answer = handleTask(updatedText)
    client.chat_postMessage(channel=channel, thread_ts=ts, text=answer)


def generate_llm_config(tool):
    # Define the function schema based on the tool's args_schema
    function_schema = {
        "name": tool.name.lower().replace(" ", "_"),
        "description": tool.description,
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    }
    if tool.args is not None:
        function_schema["parameters"]["properties"] = tool.args

    return function_schema


# The main execution of the task message takes place here
def handleTask(taskMessage):
    config_list = [
        {"model": "gpt-4-1106-preview", "api_key": os.environ["OPENAI_API_KEY"]}
    ]

    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=["https://mail.google.com/", "https://www.googleapis.com/auth/calendar"],
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)
    calender_toolkit = CalendarToolkit()

    tools = []
    function_map = {}
    for tool in toolkit.get_tools() + calender_toolkit.get_tools():  # debug_toolkit if you want to use tools directly
        tool_schema = generate_llm_config(tool)
        tools.append(tool_schema)
        function_map[tool.name] = tool._run

    # Incorporating search tool manually
    search_tool = DuckDuckGoSearchRun()

    def search_wrapper(query):
        return search_tool.run(query)

    search_tool_schema = generate_llm_config(search_tool)
    tools.append(search_tool_schema)
    function_map["duckduckgo_search"] = search_wrapper
   


    llm_config = {
        "functions": tools,
        "config_list": config_list,  # Assuming you have this defined elsewhere
        "timeout": 120,
    }
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        is_termination_msg=lambda x: x.get("content", "")
        and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        code_execution_config={
            "work_dir": "coding",
            "use_docker": False,
        },  # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
    )


    india_timezone = pytz.timezone(os.environ["TIMEZONE"])
    current_datetime_my_timezone = datetime.now(india_timezone)
    current_date_my_timezone = current_datetime_my_timezone.date()
    print(current_date_my_timezone)
    user_proxy.register_function(function_map=function_map)
    chatbot = autogen.AssistantAgent(
        name="chatbot",
        system_message="You are a personal assistant for business professionals whose name is Donna. For email related and calender related tasks only use the functions you have been provided with. The date today is {} for Calender tasks. Reply TERMINATE when the task is done.".format(current_date_my_timezone),
        llm_config=llm_config,
    )
    user_proxy.initiate_chat(
        chatbot,
        message=taskMessage,
        llm_config=llm_config,
    )

    messages = chatbot.chat_messages[user_proxy]
    totalTextOutput = ""
    for message in messages:
        if message["role"] is not None:
            totalTextOutput = totalTextOutput + message["role"] + ": "
        if message["content"] is not None:
            totalTextOutput = totalTextOutput + message["content"] + "/n"
    print("$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$")
    print(totalTextOutput)
    # Below is code to generate the final answer to return from this chat log session between user proxy and chatbot
    chat = ChatOpenAI(temperature=0, model="gpt-4-1106-preview")
    system_message_prompt = SystemMessagePromptTemplate.from_template(
        """You are a helpful assistant that extracts out an answer from a chat between a human and an AI assistant.
        In the below list of messsages from a user to an assistant, extract out and print only one answer from the chatbot that is relevant to the original user's message
        Ignore any questions from the chatbot to the user proxy, only extract the answer to the user's original query: """
    )
    human_template = "{text}"
    human_message_prompt = HumanMessagePromptTemplate.from_template(human_template)
    chat_prompt = ChatPromptTemplate.from_messages(
        [system_message_prompt, human_message_prompt]
    )

    # get a chat completion from the formatted messages
    answer = chat(
        chat_prompt.format_prompt(
            text=totalTextOutput,
        ).to_messages()
    )
    print(
        "####################################################################################"
    )
    print(answer)

    return answer.content


if __name__ == "__main__":
    print("starting server")
    serve(app, host="0.0.0.0", port=50100, threads=1)
