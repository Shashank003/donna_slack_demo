import os
from dotenv import load_dotenv
import autogen
from langchain_community.agent_toolkits import GmailToolkit
from langchain_openai import ChatOpenAI
from langchain.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from langchain_community.tools import DuckDuckGoSearchRun

load_dotenv(override=True)


def main():

    config_list = [
        {"model": "gpt-4-1106-preview", "api_key": os.environ["OPENAI_API_KEY"]}
    ]
    gmailtoolkit = GmailToolkit()
    tools = []
    function_map = {}

    for tool in gmailtoolkit.get_tools():  # debug_toolkit if you want to use tools directly
        tool_schema = generate_llm_config(tool)
        tools.append(tool_schema)
        function_map[tool.name] = tool._run

    # Incorporating search tool manually 
    search_tool = DuckDuckGoSearchRun() 
    def search_wrapper(query):
        return search_tool.run(query)
    search_tool_schema = generate_llm_config(search_tool)
    tools.append(search_tool_schema)
    function_map['duckduckgo_search'] = search_wrapper

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
    user_proxy.register_function(function_map=function_map)
    chatbot = autogen.AssistantAgent(
        name="chatbot",
        system_message="For email related tasks, only use the functions you have been provided with. Reply TERMINATE when the task is done.",
        llm_config=llm_config,
    )

    user_proxy.initiate_chat(
        chatbot,
        message="Who is Obama",
        llm_config=llm_config,
    )

    messages = chatbot.chat_messages[user_proxy]
    print(messages)
    totalTextOutput = ""
    for message in messages:
        if message["role"] is not None:
            totalTextOutput = totalTextOutput + message["role"] + ": "
        if message["content"] is not None:
            totalTextOutput = totalTextOutput + message["content"] + "/n"

    #Below is code to generate the final answer to return from this chat log session between user proxy and chatbot
    chat = ChatOpenAI(temperature=0, model="gpt-4-1106-preview")
    system_message_prompt = SystemMessagePromptTemplate.from_template(
            "You are a helpful assistant that summarizes chat sessions between a human and an AI assistant"
        )
    human_template = (
            "In the below list of messsages from a user to an assistant, extract out and print only the final output from the chatbot that answers the users question:\n {text}"
        )
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
    print("##################################################################")
    print(answer)
    # Maybe need to think of reworking this approach to handle the outputs in a better way by including the function run outputs


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


# google calender functions




if __name__ == "__main__":
    main()
