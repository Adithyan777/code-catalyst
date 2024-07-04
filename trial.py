import autogen
import agentops
import os

from autogen.agentchat.contrib.capabilities import transforms,transform_messages
from autogen import GroupChat,Agent
from typing import Union
from system_prompts import planner_prompt

# print(autogen.UserProxyAgent.DEFAULT_USER_PROXY_AGENT_DESCRIPTIONS)
# print(autogen.AssistantAgent.DEFAULT_SYSTEM_MESSAGE)
# print(autogen.GroupChatManager.DEFAULT_SUMMARY_PROMPT)

agentops_api_key = os.getenv('AGENTOPS_API_KEY')

config_list = autogen.config_list_from_dotenv(
    dotenv_file_path=".env",
    model_api_key_map={
        "gpt-4o" : "OPENAI_API_KEY",
        "gpt-3.5-turbo" : "OPENAI_API_KEY"
    }
)

# agentops.init(agentops_api_key)

llm_config = {"config_list": config_list, "cache_seed": 42}

PlannerAgent = autogen.AssistantAgent(
    "Planner",
    system_message = planner_prompt,
    llm_config = llm_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
    max_consecutive_auto_reply=1 # todo - either make it one or add termination_msg
)

def get_planning_agent_response(desc: str) -> str:
    # todo = try to improve here
    # PlannerAgent.initiate_chat(recipient=PlannerAgent,message=desc,max_turns=2)
    # return PlannerAgent.last_message()["content"]
    plan = PlannerAgent.generate_oai_reply(desc)[1]
    return plan

desc = """1. **Project Name**:
   - Chat App

2. **Programming Language**:
   - Python

3. **Dependencies and Requirements**:
   - Flask
   - python-dotenv
   - fastAPI

4. **Additional Configuration**:
   - No additional configuration required.

5. **Base Image**:
   - python:3.8

6. **Port Configuration**:
   - 8080 for fastAPI

7. **Any Additional Notes or Preferences**:
   - No additional notes or preferences."""

print(get_planning_agent_response([{
    "role" : "user",
    "content" : desc
}]))

# agentops.end_session("Success") # Success|Fail|Indeterminate
