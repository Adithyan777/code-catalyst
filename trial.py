import autogen
import agentops
import os

from autogen.agentchat.contrib.capabilities import transforms,transform_messages
from autogen import UserProxyAgent,AssistantAgent
from typing import Union
from SYS_MSG import template_agent_prompt,team_intro
from string import Template
import re

def get_sys_msg(agent_msg:str):
    temp = Template(agent_msg)
    return temp.substitute(team_intro=team_intro)

def extract_summary(text):
    # Define the regular expression pattern to match the summary
    pattern = r'### Summary:\s*(.*)'
    
    # Use the re.search() function to find the match
    match = re.search(pattern, text, re.DOTALL)
    
    # If a match is found, return the summary text, otherwise return None
    if match:
        return match.group(1).strip()
    else:
        return None

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

llm_config = {"config_list": config_list, "cache_seed": 41}

HumanProxy = UserProxyAgent(
    "human_proxy",
    llm_config = False,  # no LLM used for human proxy
    code_execution_config={
        "work_dir" : "folder",
        "use_docker" : False
    },
    human_input_mode = "NEVER",
)

TemplateAgent = AssistantAgent(
    "template_agent",
    system_message = get_sys_msg(template_agent_prompt),
    llm_config = llm_config,
    code_execution_config = False,
    human_input_mode = "NEVER", 
    is_termination_msg = lambda x: (
        isinstance(x, dict) and 
        any("exitcode: 0" in line.lower() for line in str(x.get("content", "")).splitlines()[-15:])
    )
)

print(f"API_KEY SET!")

desc = """
Here is a sample input for a JavaScript-based project:

1. **Project Name**:
   - E-commerce Website

2. **Programming Language**:
   - JavaScript

3. **Dependencies and Requirements**:
   - Express
   - Mongoose
   - dotenv

4. **Additional Configuration**:
   - Environment variables setup for database connection

5. **Base Image**:
   - node:14

6. **Port Configuration**:
   - 3000

7. **Any Additional Notes or Preferences**:
   - None
"""

result = HumanProxy.initiate_chat(
   recipient = TemplateAgent, 
   summary_method = "last_msg",
   silent = False,
   message = desc
)
# summary = extract_summary(TemplateAgent.last_message()["content"])



# agentops.end_session("Success") # Success|Fail|Indeterminate
print(result.cost)