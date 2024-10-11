import os
from dotenv import load_dotenv
from autogen import UserProxyAgent,AssistantAgent,config_list_from_dotenv,filter_config,Agent
from typing import List,Dict


import agentops

from sys_msg_docker import docker_extract_info_prompt,template_agent_prompt,tester_agent_prompt,docker_agent_prompt,compose_agent_prompt
from agent_skills import ask_human,build_and_test_docker_image,run_docker_compose_up
from helper_functions import extract_description,extract_project_name,get_sys_msg_docker,extract_summary,ask_user_input
from CustomGroupChat import CustomGroupChat,CustomGroupChatManager


load_dotenv()
monitor_agents = False

api_key = os.getenv('OPENAI_API_KEY')
agentops_api_key = os.getenv('AGENTOPS_API_KEY')
is_development = os.getenv('ENVIRONMENT') is not None

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
    "temperature" : 0,
    "cache_seed" : 49
}
gpt3_config = {
    "config_list" : filter_config(config_list,{"model" : ["gpt-3.5-turbo"]}), # filtering only the gpt-3.5-model
    "temperature" : 0
}

if monitor_agents and is_development:
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
    system_message = docker_extract_info_prompt,
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode = "NEVER", 
)

# registering tools to agents
ExtractInfoAgent.register_for_llm(name="ask_user",description="Asks user for the missing information")(ask_human)
HumanProxy.register_for_execution(name="ask_user")(ask_human)

# -----------------------------------------------------  GROUP CHAT CODE  ------------------------------------------------------------------------

stored_messages = []

def speaker_sel_func(lastspeaker:Agent,groupchat:CustomGroupChat):

    # print("reached")

    last_message = groupchat.messages[-1]["content"]
    def clear_and_extract_summary(grp_messages: List[Dict]):
        # todo - handle case when extract_summary gives None
        return {
            'name': grp_messages[-2]["name"],
            'content': f"Summary from {grp_messages[-2]["name"]}:\n" + extract_summary(grp_messages[-2]["content"]),
            'role': "assistant"
        }
            
    if lastspeaker is initializer:
        stored_messages.append(groupchat.messages[0])
        return TemplateAgent,groupchat.messages
    elif lastspeaker is TemplateAgent:
        return HumanProxyGroup,groupchat.messages
    elif lastspeaker is TesterAgent:
        return HumanProxyGroup,groupchat.messages
    elif lastspeaker is DockerAgent:
        return HumanProxyGroup,groupchat.messages
    elif lastspeaker is ComposeAgent:
        return HumanProxyGroup,groupchat.messages
    elif lastspeaker is HumanProxyGroup:
        if groupchat.messages[-2]["name"] == "TemplateAgent":
            if "exitcode: 0" in last_message:
                stored_messages.append(clear_and_extract_summary(groupchat.messages))
                groupchat.messages.clear()
                return TesterAgent,stored_messages
            else:
                return TemplateAgent,groupchat.messages
        elif groupchat.messages[-2]["name"] == "TesterAgent":
            if "exitcode: 0" in last_message:
                stored_messages.append(clear_and_extract_summary(groupchat.messages))
                groupchat.messages.clear()
                return DockerAgent,stored_messages
            else:
                return TesterAgent,groupchat.messages
        elif groupchat.messages[-2]["name"] == "DockerAgent":
            if "exitcode: 0" in last_message:
                stored_messages.append(clear_and_extract_summary(groupchat.messages))
                groupchat.messages.clear()
                return ComposeAgent,stored_messages
            else:
                return DockerAgent,groupchat.messages
        elif groupchat.messages[-2]["name"] == "ComposeAgent":
            return ComposeAgent,groupchat.messages
            # if "TERMINATE" in last_message:
            #     stored_messages.append(clear_and_extract_summary(groupchat.messages))
            #     groupchat.messages.clear()
            #     return None,None
            # else:
            #     return ComposeAgent,groupchat.messages


initializer = UserProxyAgent(
    name = "initializer",
    code_execution_config=False,
    llm_config=False,
    human_input_mode="NEVER",
)

HumanProxyGroup= UserProxyAgent(
        "HumanProxyGroup",
        llm_config = False,  # no LLM used for human proxy
        code_execution_config={
            "work_dir" : "project_code",
            "use_docker" : False,
            "last_n_messages" : 1  # todo
        },
        human_input_mode = "NEVER",
    ) 
# HumanProxyGroup.register_for_execution(name="build_and_test_docker_image")(build_and_test_docker_image)     
HumanProxyGroup.register_for_execution(name="run_docker_compose_up")(run_docker_compose_up)

TemplateAgent = AssistantAgent(
    "TemplateAgent",
    system_message = get_sys_msg_docker(template_agent_prompt),
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode = "NEVER"
)

TesterAgent = AssistantAgent(
    "TesterAgent",
    system_message = get_sys_msg_docker(tester_agent_prompt),
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
)

DockerAgent = AssistantAgent(
    "DockerAgent",
    system_message = get_sys_msg_docker(docker_agent_prompt),
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
)

ComposeAgent = AssistantAgent(
    "ComposeAgent",
    system_message= get_sys_msg_docker(compose_agent_prompt),
    llm_config=gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
)
ComposeAgent.register_for_llm(name="run_docker_compose_up",description="Run Docker Compose to build and start services.")(run_docker_compose_up)

group_chat = CustomGroupChat(
    agents=[initializer,TemplateAgent,TesterAgent,DockerAgent,ComposeAgent,HumanProxyGroup],
    messages=[],
    select_speaker_auto_verbose=True,
    speaker_selection_method=speaker_sel_func
)

group_chat_manager = CustomGroupChatManager(
        groupchat = group_chat,
        llm_config = gpt4_config
    )

# ----------------------------------------------------- CONTAINERIZATION TWO-WAY AGENT CODE -------------------------------------------------------

# todo - need to figure out how to build and run tests inside container while in the group chat OR
#        initiate a new conversation for the build and running processes




# -----------------------------------------------------  MAIN FUNCTION  ---------------------------------------------------------------------------

usr_input = """
A JavaScript-based project named "E-commerce Website," using Node.js (node:14) as the base image, dependencies include Express, Mongoose, and dotenv for environment variable management, particularly for database connectivity.
"""

usr_input2 = """
I am developing a web application called 'Chat App'. It's built using Python and requires Flask. The base image should be python:3.8.Other dependencies include dotenv and fastAPI.Also no other config required.
"""

user_input = ask_user_input()

def main():
    print(f"API_KEY SET!")
    HumanProxy.initiate_chat(
        recipient = ExtractInfoAgent, 
        summary_method = "last_msg",
        silent = True,
        message = user_input,
    )
    response = ExtractInfoAgent.last_message()["content"]
    project_desc = extract_description(response)
    project_name = extract_project_name(project_desc)
    initializer.initiate_chat(group_chat_manager,message=project_desc)
    # HumanProxyGroup.clear_history()
    # HumanProxyGroup.initiate_chat(
    #     ComposeAgent,
    #     summary_method="last_msg",
    #     message = stored_messages
    # )
    print(stored_messages)


    if monitor_agents and is_development:
        agentops.end_session("Success") # Success|Fail|Indeterminate

if __name__ == "__main__":
    main()