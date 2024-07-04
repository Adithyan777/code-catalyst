import os
from dotenv import load_dotenv
from autogen import UserProxyAgent,AssistantAgent,config_list_from_dotenv,filter_config,Agent

import agentops

from SYS_MSG import extract_info_prompt,template_agent_prompt
from agent_skills import ask_human,write_to_file,build_docker_image
from helper_functions import extract_description,extract_project_name,get_sys_msg
from CustomGroupChat import CustomGroupChat,CustomGroupChatManager
from typing import List,Dict

load_dotenv()
monitor_agents = False

api_key = os.getenv('OPENAI_API_KEY')
agentops_api_key = os.getenv('AGENTOPS_API_KEY')

if not api_key:
    # make a set api_key command using typer and ask to use it here.
    raise ValueError("API key not found. Please set the API_KEY environment variable.")

# generating config_list from env var
config_list = config_list_from_dotenv(
    dotenv_file_path=".env",
    model_api_key_map={
        "gpt-4o" : "OPENAI_API_KEY",
        "gpt-3.5-turbo" : "OPENAI_API_KEY"
    },
    filter_dict={
        "model" : {
            "gpt-4o",
            "gpt-3.5-turbo"
        }
    }
)

# generating llm_config's from config_list
gpt4_config = {
    "config_list" : filter_config(config_list,{"model" : ["gpt-4o"]}), # filtering only the gpt-4o model
    "temperature" : 0
}
gpt3_config = {
    "config_list" : filter_config(config_list,{"model" : ["gpt-3.5-turbo"]}), # filtering only the gpt-3.5-model
    "temperature" : 0
}

if monitor_agents:
    agentops.init(agentops_api_key)

# -----------------------------------------------------  EXTRACT INFO 2-WAY AGENT CODE  ----------------------------------------------------------

HumanProxy = UserProxyAgent(
    "human_proxy",
    llm_config = False,  # no LLM used for human proxy
    human_input_mode = "NEVER",
    is_termination_msg = lambda x: (
        isinstance(x, dict) and 
        any("TERMINATE" in line.upper() for line in str(x.get("content", "")).splitlines()[-15:])
    )
)

ExtractInfoAgent = AssistantAgent(
    "info_extracter",
    system_message = extract_info_prompt,
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode = "NEVER", 
)

# registering tools to agents
ExtractInfoAgent.register_for_llm(name="ask_user",description="Asks user for the missing information")(ask_human)
HumanProxy.register_for_execution(name="ask_user")(ask_human)

# -----------------------------------------------------  GROUP CHAT CODE  ------------------------------------------------------------------------

def speaker_sel_func(lastspeaker:Agent,groupchat:CustomGroupChat):

    mess = groupchat.messages
    last_mess = mess[-1]["content"]
    def clear_and_append(mess:List[Dict],last:int = 1):
        num = mess[-last:]
        mess.clear()
        for i in num:
            mess.append(i)
        
    if lastspeaker is initializer:
        clear_and_append(mess)
        return TemplateAgent,groupchat.messages
    elif lastspeaker is TemplateAgent:
        return HumanProxyGroup,groupchat.messages
    elif lastspeaker is HumanProxy:
        if(len(mess) > 1):
            print(mess[-2]["name"])
        if "exitcode: 0" in last_mess:
            clear_and_append(mess)
            return None,None
        else:
            return TemplateAgent

initializer = UserProxyAgent(
    name = "init",
    code_execution_config=False,
    llm_config=False,
    human_input_mode="NEVER" 
)

HumanProxyGroup= UserProxyAgent(
        "human_proxy",
        llm_config = False,  # no LLM used for human proxy
        code_execution_config={
            "work_dir" : "main",
            "use_docker" : False
        },
        human_input_mode = "NEVER",
    )      

TemplateAgent = AssistantAgent(
    "template_agent",
    system_message = get_sys_msg(template_agent_prompt),
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode = "NEVER", 
    is_termination_msg = lambda x: (
        isinstance(x, dict) and 
        any("exitcode: 0" in line.lower() for line in str(x.get("content", "")).splitlines()[-15:])
    )
)


# DockerFileAgent = AssistantAgent(
#     "DockerFileAgent",
#     system_message = docker_agent_prompt,
#     llm_config = gpt4_config,
#     code_execution_config = False,
#     human_input_mode= "NEVER",
# )

# TesterAgent = AssistantAgent(
#     "TesterAgent",
#     system_message = tester_agent_prompt,
#     llm_config = gpt4_config,
#     code_execution_config = False,
#     human_input_mode= "NEVER",
# )

# ToolExecutionAgent = AssistantAgent(
#         "ToolExecutionAgent",
#         system_message = tool_execution_agent_prompt,
#         llm_config = gpt4_config,
#         human_input_mode= "NEVER",
#     )
# ToolExecutionAgent.register_for_llm(description="Function to write content to a file and save it on the machine.")(write_to_file)
# ToolExecutionAgent.register_for_llm(description="Function to build a Docker image from a Dockerfile present in the current directory.")(build_docker_image)



# # Adding agent descriptions
# def add_agent_descriptions(HumanProxyGroup:UserProxyAgent):
#     DockerFileAgent.description = "Generates and debugs the Dockerfile in case of errors"
#     TemplateCodeAgent.description = "Generates and debugs the boilerplate code in case of errors"
#     TesterAgent.description = "Generates and debugs project-specific tests in case of errors"
#     ToolExecutionAgent.description = "Has access to tools."
#     HumanProxyGroup.description = "Executes the tools given by ToolExecutionAgent." 
#     # ContainerAgent: Runs tests inside the container. [todo]

group_chat = CustomGroupChat(
    agents=[initializer,TemplateAgent,HumanProxyGroup],
    messages=[],
    select_speaker_auto_verbose=True,
    speaker_selection_method=speaker_sel_func
)

group_chat_manager = CustomGroupChatManager(
        groupchat = group_chat,
        llm_config = gpt4_config
    )

# -----------------------------------------------------  MAIN FUNCTION  ---------------------------------------------------------------------------

#  message = "I am developing a web application called 'Chat App'. It's built using Python and requires Flask. The base image should be python:3.8.Other dependencies include dotenv and fastAPI.Also no other config required.",

def main():
    print(f"API_KEY SET!")
    HumanProxy.initiate_chat(
        recipient = ExtractInfoAgent, 
        summary_method = "last_msg",
        silent = True,
        message = "I am developing a web application called 'Chat App'. It's built using Python and requires Flask. The base image should be python:3.8.Other dependencies include dotenv and fastAPI.Also no other config required.",
    )
    response = ExtractInfoAgent.last_message()["content"]
    project_desc = extract_description(response)
    project_name = extract_project_name(project_desc)
    initializer.initiate_chat(group_chat_manager,message=project_desc)


    if monitor_agents:
        agentops.end_session("Success") # Success|Fail|Indeterminate

if __name__ == "__main__":
    main()