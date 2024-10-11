import os
from dotenv import load_dotenv
from autogen import UserProxyAgent,AssistantAgent,Agent
from typing import List,Dict
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, TextColumn

import agentops

from sys_msg_docker import docker_extract_info_prompt,docker_template_agent_prompt,docker_tester_agent_prompt,compose_agent_prompt,docker_agent_prompt
from helper_functions import extract_description,get_sys_msg_docker,extract_summary
from CustomGroupChat import CustomGroupChat,CustomGroupChatManager
from agent_skills import ask_human,run_docker_compose_up


load_dotenv()
monitor_agents = False
agentops_api_key = os.getenv('AGENTOPS_API_KEY')
is_development = os.getenv('ENVIRONMENT') is not None


if monitor_agents and is_development:
    agentops.init(agentops_api_key)

progress = Progress(
    SpinnerColumn(finished_text="✅"),
    TextColumn("[progress.description]{task.description}"),
    TimeElapsedColumn(),
)

# Function to add a task to the Progress object if it doesn't already exist.
tasks = {}
def add_task_if_not_exists(task_no, description, total=100):
    if task_no not in tasks:
        task_id = progress.add_task(description, total=total)
        tasks[task_no] = (description, task_id)
        return task_id
    else:
        return tasks[task_no][1]


# Main function to initiate chat with multi-agents
def initiate_multi_agents_docker(api_key, project_name, project_description, console):

    llm_config = {
        "config_list": [
            {"model": "gpt-4o", "api_key": api_key },
            {"model": "gpt-3.5-turbo", "api_key": api_key }
        ],
        "temperature" : 0,
        "cache_seed" : 57
    }

    # -----------------------------------------------------  EXTRACT INFO 2-WAY AGENT CODE  -----------------------------------------------------

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
        llm_config = llm_config,
        code_execution_config = False,
        human_input_mode = "NEVER", 
    )

    # registering tools to agents
    ExtractInfoAgent.register_for_llm(name="ask_user",description="Asks user for the missing information")(ask_human)
    HumanProxy.register_for_execution(name="ask_user")(ask_human)

    chat_input = f"Project Name: {project_name}\nProject Description: {project_description}"
    HumanProxy.initiate_chat(
        recipient = ExtractInfoAgent, 
        summary_method = "last_msg",
        silent = True,
        message = chat_input,
    )
    response = ExtractInfoAgent.last_message()["content"]
    extracted_desc = extract_description(response)
    progress.start()
    task2 = progress.add_task("[dark_orange3]Waking up the agents...  🤖                     ", total=100)
    
# -----------------------------------------------------  GROUP CHAT CODE  ------------------------------------------------------------------------

    stored_messages = []

    def speaker_sel_func(lastspeaker:Agent,groupchat:CustomGroupChat):

        last_message = groupchat.messages[-1]["content"]
        def clear_and_extract_summary(grp_messages: List[Dict]):
            # todo - handle case when extract_summary gives None
            return {
                'name': grp_messages[-2]["name"],
                'content': f"Summary from {grp_messages[-2]["name"]}:\n" + extract_summary(grp_messages[-2]["content"]),
                'role': "assistant"
            }
                
        if lastspeaker is initializer:
            task3 = add_task_if_not_exists(3,"[dark_orange3]Adding the boileplate code... 🪄")
            stored_messages.append(groupchat.messages[0])
            return TemplateAgent,groupchat.messages
        elif lastspeaker is TemplateAgent:
            return HumanProxyGroup,groupchat.messages
        elif lastspeaker is TesterAgent:
            return HumanProxyGroup,groupchat.messages
        elif lastspeaker is DockerAgent:
            return HumanProxyGroup,groupchat.messages
        # elif lastspeaker is ComposeAgent:
        #     return HumanProxyGroup,groupchat.messages
        elif lastspeaker is HumanProxyGroup:
            if groupchat.messages[-2]["name"] == "TemplateAgent":
                if "exitcode: 0" in last_message:
                    stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    progress.update(tasks[3][1], advance=100)
                    task4 = add_task_if_not_exists(4,"[dark_orange3]Adding the test files...  🧪")
                    return TesterAgent,stored_messages
                else:
                    return TemplateAgent,groupchat.messages
            elif groupchat.messages[-2]["name"] == "TesterAgent":
                if "exitcode: 0" in last_message:
                    # progress.stop()
                    stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    progress.update(tasks[4][1], advance=100)
                    task5 = add_task_if_not_exists(5,"[dark_orange3]Adding the Docker files...  🐳")
                    return DockerAgent,stored_messages
                else:
                    return TesterAgent,groupchat.messages
            elif groupchat.messages[-2]["name"] == "DockerAgent":
                if "exitcode: 0" in last_message:
                    stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    progress.update(tasks[5][1], advance=100)
                    progress.stop()
                    # task6 = add_task_if_not_exists(6,"[dark_orange3]Building and running the Docker container...  🚀")
                    return None,None
                else:
                    return DockerAgent,groupchat.messages
            # elif groupchat.messages[-2]["name"] == "ComposeAgent":
            #     return ComposeAgent,groupchat.messages
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
                "work_dir" : ".",
                "use_docker" : False,
                "last_n_messages" : 1  # todo
            },
            human_input_mode = "NEVER",
        ) 

    TemplateAgent = AssistantAgent(
        "TemplateAgent",
        system_message = get_sys_msg_docker(docker_template_agent_prompt),
        llm_config = llm_config,
        code_execution_config = False,
        human_input_mode = "NEVER"
    )

    TesterAgent = AssistantAgent(
        "TesterAgent",
        system_message = get_sys_msg_docker(docker_tester_agent_prompt),
        llm_config = llm_config,
        code_execution_config = False,
        human_input_mode= "NEVER",
    )

    DockerAgent = AssistantAgent(
        "DockerAgent",
        system_message = get_sys_msg_docker(docker_agent_prompt),
        llm_config = llm_config,
        code_execution_config = False,
        human_input_mode= "NEVER",
    )

    # ComposeAgent = AssistantAgent(
    #     "ComposeAgent",
    #     system_message= get_sys_msg_docker(compose_agent_prompt),
    #     llm_config=llm_config,
    #     code_execution_config = False,
    #     human_input_mode= "NEVER",
    # )
    # ComposeAgent.register_for_llm(name="run_docker_compose_up",description="Run Docker Compose to build and start services.")(run_docker_compose_up)

    group_chat = CustomGroupChat(
        agents=[initializer,TemplateAgent,TesterAgent,DockerAgent,HumanProxyGroup],
        messages=[],
        select_speaker_auto_verbose=False,
        speaker_selection_method=speaker_sel_func
    )

    group_chat_manager = CustomGroupChatManager(
            groupchat = group_chat,
            llm_config = llm_config,
            silent=True
    )
    progress.update(task2, advance=100)

    # -----------------------------------------------------  INITIATING AGENTS  ---------------------------------------------------------------------

    
    initializer.initiate_chat(group_chat_manager,message=extracted_desc,silent=True)


#     if monitor_agents and is_development:
#         agentops.end_session("Success") # Success|Fail|Indeterminate 