import os
import slack_sdk as slack
from flask import Flask, request, jsonify
from flask import make_response
from slackeventsapi import SlackEventAdapter
from waitress import serve
from flask_cors import CORS
import threading
import autogen
from langchain_community.tools.gmail.utils import (
    build_resource_service,
    get_gmail_credentials,
)
from langchain_core.prompts.chat import ChatPromptTemplate
from langchain_community.agent_toolkits import GmailToolkit
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain import hub
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
CORS(app) 

eventAdapter = SlackEventAdapter(
    os.environ["SLACK_SIGNING_SECRET"], "/slack/events", app
)

client = slack.WebClient(token=os.environ["SLACK_BOT_TOKEN"])

bot = client.api_call("auth.test")["user_id"]


# The api endpoint for the agentsy mvp demo
@app.route('/donnaChat', methods=['POST'])
def handle_post():
    # Check if the request contains JSON
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400
    
    data = request.get_json()    
    # Validate that 'taskMessage' is in the data
    if "taskMessage" not in data:
        return jsonify({"error": "Missing 'taskMessage' in request"}), 400

    # Process the task message
    task_message = data["taskMessage"]
    print(task_message) 
    answer = handleTask(taskMessage=task_message)

    # Return the processed answer in the response
    # Modify this according to how you want to structure your response
    return jsonify({"answer": answer}), 200

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
    updatedText = text.replace("<@" + bot + ">", "")
    answer = handleTask(updatedText)
    client.chat_postMessage(channel=channel, thread_ts=ts, text=answer)


# def generate_llm_config(tool):
#     # Define the function schema based on the tool's args_schema
#     function_schema = {
#         "name": tool.name.lower().replace(" ", "_"),
#         "description": tool.description,
#         "parameters": {
#             "type": "object",
#             "properties": {},
#             "required": [],
#         },
#     }
#     if tool.args is not None:
#         function_schema["parameters"]["properties"] = tool.args

#     return function_schema


# The main execution of the task message takes place here
def handleTask(taskMessage):
    model = ChatOpenAI(model="gpt-4-1106-preview", temperature=0)

    credentials = get_gmail_credentials(
        token_file="token.json",
        scopes=["https://mail.google.com/", "https://www.googleapis.com/auth/calendar"],
        client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)
    calender_toolkit = CalendarToolkit()
    search_tool = DuckDuckGoSearchRun()
    tools = []
    tools = tools + toolkit.get_tools() + calender_toolkit.get_tools()
    tools.append(search_tool)
    prompt = hub.pull("hwchase17/openai-tools-agent")

    india_timezone = pytz.timezone(os.environ["TIMEZONE"])
    current_datetime_my_timezone = datetime.now(india_timezone)
    current_date_my_timezone = current_datetime_my_timezone.date()
    print(current_date_my_timezone)
    for index, message in enumerate(prompt.messages):
        if isinstance(message, SystemMessagePromptTemplate):
            # Modify the template of the SystemMessagePromptTemplate
            # This step depends on the actual structure and attributes of SystemMessagePromptTemplate
            # Assuming it has a `prompt` attribute which in turn has a `template` attribute
            new_template = 'You are a helpful assistant called Donna. Please note the current date is {} for any calendar-related tasks'.format(current_date_my_timezone)
            prompt.messages[index].prompt.template = new_template
            break 
    agent = create_openai_tools_agent(model, tools, prompt=prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    answer = agent_executor.invoke(
    {
        "input": taskMessage
    }
)
    print("#######################################################################")
    return answer["output"]


if __name__ == "__main__":
    print("starting server")
    serve(app, host="0.0.0.0", port=50100, threads=1)
