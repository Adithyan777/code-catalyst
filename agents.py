import os
from dotenv import load_dotenv
from autogen import UserProxyAgent,AssistantAgent,config_list_from_dotenv,filter_config,GroupChatManager

import agentops

from system_prompts import extract_info_prompt,planner_prompt,docker_agent_prompt,template_agent_prompt,tester_agent_prompt,tool_execution_agent_prompt,next_role_prompt_first,next_role_prompt_last
from agent_skills import ask_human,write_to_file,build_docker_image
from helper_functions import extract_prompt,extract_project_name
from CustomGroupChat import CustomGroupChat,CustomGroupChatManager

load_dotenv()
monitor_agents = True

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

PlannerAgent = AssistantAgent(
    "Planner",
    system_message = planner_prompt,
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
    max_consecutive_auto_reply = 1 # todo - either make it one or add termination_msg
)

def get_planning_agent_response(desc: str) -> str:
    # PlannerAgent.initiate_chat(recipient=PlannerAgent,message=desc,max_turns=2)
    # return PlannerAgent.last_message()["content"]
    plan = PlannerAgent.generate_oai_reply([{
        "role" : "user",
        "content" : desc
    }])[1]
    return plan


DockerFileAgent = AssistantAgent(
    "DockerFileAgent",
    system_message = docker_agent_prompt,
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
)

TemplateCodeAgent = AssistantAgent(
    "TemplateCodeAgent",
    system_message = template_agent_prompt,
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
)

TesterAgent = AssistantAgent(
    "TesterAgent",
    system_message = tester_agent_prompt,
    llm_config = gpt4_config,
    code_execution_config = False,
    human_input_mode= "NEVER",
)

ToolExecutionAgent = AssistantAgent(
        "ToolExecutionAgent",
        system_message = tool_execution_agent_prompt,
        llm_config = gpt4_config,
        human_input_mode= "NEVER",
    )
ToolExecutionAgent.register_for_llm(description="Function to write content to a file and save it on the machine.")(write_to_file)
ToolExecutionAgent.register_for_llm(description="Function to build a Docker image from a Dockerfile present in the current directory.")(build_docker_image)

def instantiate_executor_agent(project_name :str) -> UserProxyAgent:
    HumanProxyGroup =  UserProxyAgent(
    "human_proxy",
    llm_config = False,  # no LLM used for human proxy
    human_input_mode = "NEVER",
    code_execution_config = {
            "last_n_messages": 2,
            "work_dir": project_name,
            "use_docker": False,
        },
    is_termination_msg = lambda x: (
        isinstance(x, dict) and 
        any("TERMINATE" in line.upper() for line in str(x.get("content", "")).splitlines()[-15:])
    )
    )
    HumanProxyGroup.register_for_execution()(write_to_file)
    HumanProxyGroup.register_for_execution()(build_docker_image)
    
    return HumanProxyGroup

# Adding agent descriptions
def add_agent_descriptions(HumanProxyGroup:UserProxyAgent):
    DockerFileAgent.description = "Generates and debugs the Dockerfile in case of errors"
    TemplateCodeAgent.description = "Generates and debugs the boilerplate code in case of errors"
    TesterAgent.description = "Generates and debugs project-specific tests in case of errors"
    ToolExecutionAgent.description = "Has access to tools."
    HumanProxyGroup.description = "Executes the tools given by ToolExecutionAgent." 
    # ContainerAgent: Runs tests inside the container. [todo]

def instantiate_groupchat(plan :str,HumanProxyGroup :UserProxyAgent) -> CustomGroupChat:

    constraints = {
            TemplateCodeAgent: [ToolExecutionAgent],
            TesterAgent: [ToolExecutionAgent],
            DockerFileAgent: [ToolExecutionAgent],
            ToolExecutionAgent: [TemplateCodeAgent,TesterAgent,DockerFileAgent,HumanProxyGroup],
            HumanProxyGroup : [TemplateCodeAgent,TesterAgent,DockerFileAgent,ToolExecutionAgent]
    }
    # todo - add Constrained Speaker Selection
    groupChat = CustomGroupChat(
        agents = [TemplateCodeAgent,TesterAgent,DockerFileAgent,ToolExecutionAgent,HumanProxyGroup],
        messages = [],
        max_round = 17,
        allowed_or_disallowed_speaker_transitions = constraints,
        speaker_transitions_type = "allowed", 
        select_speaker_message_template = next_role_prompt_first,
        select_speaker_prompt_template = next_role_prompt_last,
        # select_speaker_auto_multiple_template = ,
        # select_speaker_auto_none_template = ,
        input_plan=plan
    )
    return groupChat

# -----------------------------------------------------  MAIN FUNCTION  ---------------------------------------------------------------------------

def main():
    print(f"API_KEY SET!")
    HumanProxy.initiate_chat(
        recipient = ExtractInfoAgent, 
        summary_method = "last_msg",
        silent = True,
        message = "I am developing a web application called 'Chat App'. It's built using Python and requires Flask. The base image should be python:3.8.Other dependencies include dotenv and fastAPI.Also no other config required.",
    )
    response = ExtractInfoAgent.last_message()["content"]
    project_desc = extract_prompt(response)
    project_name = extract_project_name(project_desc)
    plan = get_planning_agent_response(project_desc)
    HumanProxyGroup = instantiate_executor_agent(project_name)
    add_agent_descriptions(HumanProxyGroup)
    groupChat = instantiate_groupchat(plan,HumanProxyGroup)

    groupChatManager = CustomGroupChatManager(groupchat = groupChat , llm_config=gpt4_config)

    groupChatManager.initiate_chat(
        groupChatManager,
        silent=False,
        message="START."        
    )

    if monitor_agents:
        agentops.end_session("Success") # Success|Fail|Indeterminate

if __name__ == "__main__":
    main()