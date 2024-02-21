#For some weird reason some of the tools dont work in the gmail toolkit with crew ai

import os
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
from langchain_community.agent_toolkits import GmailToolkit
from langchain_openai.chat_models import ChatOpenAI

load_dotenv(override=True)

def main():
    toolkit = GmailToolkit()
    for tool in toolkit.get_tools():  # debug_toolkit if you want to use tools directly
        # print(tool.name)
        pass
        # tools.append(tool_schema)
        # function_map[tool.name] = tool._run
    
    email_agent = Agent(
  role='Email Writer',
  goal='Write formal business emails',
  backstory='An email writed who drafts, finds, and manages all email related tasks',
  tools=toolkit.get_tools(),
  llm=ChatOpenAI(model_name='gpt-4-1106-preview', temperature=0.7),
)
    task = Task(
    description='Draft an email to tacmorris@gmail.com that the meeting time has shifted to 11 pm',
    agent=email_agent
)
    crew = Crew(
    agents=[email_agent],
    tasks=[task],
    verbose=2
)
    result = crew.kickoff()
    print(result)

if __name__ == "__main__":
    main()