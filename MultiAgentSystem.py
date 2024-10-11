import os
from autogen import UserProxyAgent,AssistantAgent,Agent,register_function
from typing import List,Dict
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn, TextColumn

import agentops
from sys_msg_docker import docker_extract_info_prompt,docker_template_agent_prompt,docker_tester_agent_prompt,docker_agent_prompt,compose_agent_prompt
from sys_msg_normal import normal_extract_info_agent,template_agent_prompt,tester_agent_prompt
from helper_functions import extract_description,get_sys_msg_normal,get_sys_msg_docker,extract_summary
from CustomGroupChat import CustomGroupChat,CustomGroupChatManager
from agent_skills import ask_human

agentops_api_key = os.getenv('AGENTOPS_API_KEY')

class MultiAgentSystem:
    def __init__(self, api_key: str, console: Console, monitor_agents: bool = False,env_type: str = "normal"):
        self.api_key = api_key
        self.monitor_agents = monitor_agents
        self.stored_messages = []
        self.console = console
        self.env_type = env_type
        self.progress = Progress(
            SpinnerColumn(finished_text="✅"),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=self.console
        )
        self.tasks = {}
        self.llm_config = {
            "config_list": [
                {"model": "gpt-4", "api_key": self.api_key},
                {"model": "gpt-3.5-turbo", "api_key": self.api_key},
                # {"model":"claude-3-5-sonnet-20240620","api_key":os.getenv("ANTHROPIC_API_KEY"),"api_type":"anthropic"}
                # todo - make api_key handling and model_selection in the main.py
            ],
            "temperature": 0,
            "cache_seed": 56
        }

    def add_task(self, task_no: int, description: str, total: int = 100) -> int:
        if task_no not in self.tasks:
            task_id = self.progress.add_task(description, total=total)
            self.tasks[task_no] = (description, task_id)
            return task_id
        return self.tasks[task_no][1]
    
    def add_task_if_not_exists(self, task_no, description, total=100):
        if task_no not in self.tasks:
            task_id = self.progress.add_task(description, total=total)
            self.tasks[task_no] = (description, task_id)
            return task_id
        else:
            return self.tasks[task_no][1]
    
    def _create_base_agents(self):
        # Human Proxy that calls the tool to ask for human input
        self.human_proxy = UserProxyAgent(
            "human_proxy",
            llm_config=False,
            human_input_mode="NEVER",
            is_termination_msg=lambda x: (
                isinstance(x, dict) and 
                any("TERMINATE" in line.upper() for line in str(x.get("content", "")).splitlines()[-15:])
            )
        )

        self.extract_info_agent = AssistantAgent( 
            "info_extracter",
            system_message = normal_extract_info_agent if self.env_type == "normal" else docker_extract_info_prompt,
            llm_config = self.llm_config,
            code_execution_config = False,
            human_input_mode = "NEVER",
        )      

        register_function(
            f=ask_human,
            caller=self.extract_info_agent,
            executor=self.human_proxy,
            name="ask_user",
            description="Asks user for the missing information"
        )

    def _create_agents(self):
        # Create all your agents here
        self.initializer = UserProxyAgent(
            name = "initializer",
            code_execution_config=False,
            llm_config=False,
            human_input_mode="NEVER",
        )

        self.human_proxy_group = UserProxyAgent(
            "HumanProxyGroup",
            llm_config = False,  # no LLM used for human proxy
            code_execution_config={
                "work_dir" : ".",    # todo - change here to the correct work_dir
                "use_docker" : False,
                "last_n_messages" : 1  # todo
            },
            human_input_mode = "NEVER",
        ) 
        
        # Add other agents based on env_type
        if self.env_type == "normal":
            self.create_normal_agents()
        elif self.env_type == "docker":
            self.create_docker_agents()

    def create_normal_agents(self):
        
        self.template_agent = AssistantAgent(
            "TemplateAgent",
            system_message=get_sys_msg_normal(template_agent_prompt),
            llm_config=self.llm_config,
            code_execution_config=False,
            human_input_mode="NEVER"
        )
        
        self.tester_agent = AssistantAgent(
            "TesterAgent",
            system_message = get_sys_msg_normal(tester_agent_prompt),
            llm_config = self.llm_config,
            code_execution_config = False,
            human_input_mode= "NEVER",
        )

    def create_docker_agents(self):
        self.template_agent = AssistantAgent(
            "TemplateAgent",
            system_message = get_sys_msg_docker(docker_template_agent_prompt),
            llm_config = self.llm_config,
            code_execution_config = False,
            human_input_mode = "NEVER"
        )

        self.tester_agent = AssistantAgent(
            "TesterAgent",
            system_message = get_sys_msg_docker(docker_tester_agent_prompt),
            llm_config = self.llm_config,
            code_execution_config = False,
            human_input_mode= "NEVER",
        )

        self.docker_agent = AssistantAgent(
            "DockerAgent",
            system_message = get_sys_msg_docker(docker_agent_prompt),
            llm_config = self.llm_config,
            code_execution_config = False,
            human_input_mode= "NEVER",
        )

    def _setup_group_chat(self):
        if self.env_type == "normal":
            self.group_chat = CustomGroupChat(
                agents=[self.initializer, self.template_agent, self.tester_agent, self.human_proxy_group],
                messages=[],
                select_speaker_auto_verbose=False,
                speaker_selection_method=self.speaker_selection_function
            )
            self.group_chat_manager = CustomGroupChatManager(
                groupchat=self.group_chat,
                llm_config=self.llm_config,
                silent=True
            )
        elif self.env_type == "docker":
            self.group_chat = CustomGroupChat(
                agents=[self.initializer, self.template_agent, self.tester_agent, self.docker_agent, self.human_proxy_group],
                messages=[],
                select_speaker_auto_verbose=False,
                speaker_selection_method=self.speaker_selection_function
            )
            self.group_chat_manager = CustomGroupChatManager(
                groupchat=self.group_chat,
                llm_config=self.llm_config,
                silent=True
            )

    def speaker_selection_function_docker(self, lastspeaker: Agent, groupchat: CustomGroupChat):

        last_message = groupchat.messages[-1]["content"]
        def clear_and_extract_summary(grp_messages: List[Dict]):
            # todo - handle case when extract_summary gives None
            return {
                'name': grp_messages[-2]["name"],
                'content': f"Summary from {grp_messages[-2]["name"]}:\n" + extract_summary(grp_messages[-2]["content"]),
                'role': "assistant"
            }
                
        if lastspeaker is self.initializer:
            task3 = self.add_task_if_not_exists(3,"[dark_orange3]Adding the boileplate code... 🪄")
            self.stored_messages.append(groupchat.messages[0])
            return self.template_agent,groupchat.messages
        elif lastspeaker is self.template_agent:
            return self.human_proxy_group,groupchat.messages
        elif lastspeaker is self.tester_agent:
            return self.human_proxy_group,groupchat.messages
        elif lastspeaker is self.docker_agent:
            return self.human_proxy_group,groupchat.messages
        # elif lastspeaker is ComposeAgent:
        #     return HumanProxyGroup,groupchat.messages
        elif lastspeaker is self.human_proxy_group:
            if groupchat.messages[-2]["name"] == "TemplateAgent":
                if "exitcode: 0" in last_message:
                    self.stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    self.progress.update(self.tasks[3][1], advance=100)
                    task4 = self.add_task_if_not_exists(4,"[dark_orange3]Adding the test files...  🧪")
                    return self.tester_agent,self.stored_messages
                else:
                    return self.template_agent,groupchat.messages
            elif groupchat.messages[-2]["name"] == "TesterAgent":
                if "exitcode: 0" in last_message:
                    # progress.stop()
                    self.stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    self.progress.update(self.tasks[4][1], advance=100)
                    task5 = self.add_task_if_not_exists(5,"[dark_orange3]Adding the Docker files...  🐳")
                    return self.docker_agent,self.stored_messages
                else:
                    return self.tester_agent,groupchat.messages
            elif groupchat.messages[-2]["name"] == "DockerAgent":
                if "exitcode: 0" in last_message:
                    self.stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    self.progress.update(self.tasks[5][1], advance=100)
                    self.progress.stop()
                    # task6 = add_task_if_not_exists(6,"[dark_orange3]Building and running the Docker container...  🚀")
                    return None,None
                else:
                    return self.docker_agent,groupchat.messages
            # elif groupchat.messages[-2]["name"] == "ComposeAgent":
            #     return ComposeAgent,groupchat.messages
                # if "TERMINATE" in last_message:
                #     stored_messages.append(clear_and_extract_summary(groupchat.messages))
                #     groupchat.messages.clear()
                #     return None,None
                # else:
                #     return ComposeAgent,groupchat.messages

    def speaker_selection_function_normal(self, last_speaker: Agent, groupchat: CustomGroupChat): 
        last_message = groupchat.messages[-1]["content"]
        def clear_and_extract_summary(grp_messages: List[Dict]):
            # todo - handle case when extract_summary gives None
            return {
                'name': grp_messages[-2]["name"],
                'content': f"Summary from {grp_messages[-2]["name"]}:\n" + extract_summary(grp_messages[-2]["content"]),
                'role': "assistant"
            }
                
        if last_speaker is self.initializer:
            task3 = self.add_task_if_not_exists(3,"[dark_orange3]Adding the boileplate code... 🪄")
            self.stored_messages.append(groupchat.messages[0])
            return self.template_agent,groupchat.messages
        elif last_speaker is self.template_agent:
            return self.human_proxy_group,groupchat.messages
        elif last_speaker is self.tester_agent:
            return self.human_proxy_group,groupchat.messages
        elif last_speaker is self.human_proxy_group:
            if groupchat.messages[-2]["name"] == "TemplateAgent":
                if "exitcode: 0" in last_message:
                    self.stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    self.progress.update(self.tasks[3][1], advance=100)
                    task4 = self.add_task_if_not_exists(4,"[dark_orange3]Adding the test files...  🧪")
                    return self.tester_agent,self.stored_messages
                else:
                    return self.template_agent,groupchat.messages
            elif groupchat.messages[-2]["name"] == "TesterAgent":
                if "exitcode: 0" in last_message:
                    self.progress.update(self.tasks[4][1], advance=100)
                    self.progress.stop()
                    self.stored_messages.append(clear_and_extract_summary(groupchat.messages))
                    groupchat.messages.clear()
                    return None,None
                else:
                    return self.tester_agent,groupchat.messages
                
    def speaker_selection_function(self, last_speaker: Agent, groupchat: CustomGroupChat):
        try:
            if self.env_type == "normal":
                return self.speaker_selection_function_normal(last_speaker, groupchat)
            elif self.env_type == "docker":
                return self.speaker_selection_function_docker(last_speaker, groupchat)
        except Exception as e:
            self.console.print(f"[red]Error in speaker selection: {str(e)}[/red]")
            return None, None

    def run(self, project_name: str, project_description: str):
        try:
            self._create_base_agents()
            if self.monitor_agents:
                agentops.init(agentops_api_key)
            
            # First, handle all user interactions without progress display
            self.console.print("[cyan]Gathering project information...[/cyan]")
            chat_input = f"Project Name: {project_name}\nProject Description: {project_description}"
            
            try:
                self.human_proxy.initiate_chat(
                    recipient=self.extract_info_agent,
                    message=chat_input,
                    silent=True
                )
            except Exception as e:
                self.console.print(f"[red]Error during information extraction: {str(e)}[/red]")
                return

            extracted_desc = extract_description(self.extract_info_agent.last_message()["content"])

            with self.progress:
                self.console.print("\n[cyan]Starting project generation...[/cyan]")
                
                # Setup agents
                task1 = self.add_task(1, "[dark_orange3]Waking up the agents... 🤖")
                self._create_agents()
                self._setup_group_chat()
                self.progress.update(task1, advance=100)

                # Start the group chat
                try:
                    self.initializer.initiate_chat(
                        self.group_chat_manager,
                        message=extracted_desc,
                        silent=True
                    )
                except Exception as e:
                    self.console.print(f"[red]Error during agent conversation: {str(e)}[/red]")
        except Exception as e:
            self.console.print(f"[red]Error during execution: {str(e)}[/red]")
        finally:
            if self.monitor_agents:
                agentops.end_session("Success")
