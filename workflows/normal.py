from enum import Enum
from phi.workflow import Workflow, RunResponse, RunEvent
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.utils.log import logger
from typing import Iterable, Iterator,List,Dict,Any
import time
from phi.utils.pprint import pprint_run_response
from pydantic import Field,BaseModel
import sys,os,subprocess
from phi.utils.timer import Timer
import json
from prompts.prompt_manager import PromptManager
from rich.console import Console

from utils import CommandExecutor, Command, CommandGroup, CommandResponse, ExecutionMode, FailedCommand, FailedGroup
from tools.ask_user import ask_human
import re

monitor_agents: bool = True
model_to_use : str = 'gpt-4o-mini-2024-07-18'

class NormalSetupWorkflow(Workflow):
    apikey: str = Field(...)
    console: Console = Field(...)
    executor: CommandExecutor = Field(None)
    extractor: Agent = Field(None)
    template_agent: Agent = Field(None)
    tester_agent: Agent = Field(None)
    messages : List[Dict[str, Any]] = Field(default_factory=list)
    
    def __init__(self, apikey: str, console: Console, **data):
        super().__init__(apikey=apikey, console=console, **data)
        self.executor = CommandExecutor(console)
        # --------------------------------------
        # DEFINE AGENTS HERE (DO NOT FORGET TO ADD THEM ABOVE)
        # --------------------------------------
        self.extractor = Agent(
            name="extractor",
            model=OpenAIChat(model=model_to_use, api_key=self.apikey),
            system_prompt=PromptManager.get_prompt("extract_info_agent", setup="normal"),
            tools=[ask_human],
            monitoring=monitor_agents
        )

        self.template_agent = Agent(
            name="template_agent",
            model=OpenAIChat(model=model_to_use, api_key=self.apikey),
            system_prompt=PromptManager.get_prompt("template_agent", setup="normal"),
            structured_outputs=True,
            output_model=CommandResponse,
            monitoring=monitor_agents
        )

        self.tester_agent = Agent(
            name="tester_agent",
            model=OpenAIChat(model=model_to_use, api_key=self.apikey),
            system_prompt=PromptManager.get_prompt("tester_agent", setup="normal"),
            structured_outputs=True,
            output_model=CommandResponse,
            monitoring=monitor_agents
        )

    def execute_commands(self, commands_data: CommandResponse, mode: ExecutionMode, project_name: str) -> None:
        if mode == ExecutionMode.SAVE_SCRIPT:
            script_path = self.executor.save_as_script(commands_data.groups, project_name)
            self.console.print(f"\n[bold green]Script saved as:[/bold green] {script_path}")
            return

        execution_result = self.executor.execute_command_groups(commands_data, mode)
        failed_groups: List[FailedGroup] = execution_result["failed_groups"]
        # Handle failed groups
        if failed_groups:
            self.console.print("\n[bold red]Failed Commands Summary:[/bold red]")
            for failed_group in failed_groups:
                self.console.print(f"\n[bold yellow]Group:[/bold yellow] {failed_group.group_name}")
                self.console.print(f"[bold yellow]Description:[/bold yellow] {failed_group.description}")
                
                for failed_cmd in failed_group.failed_commands:
                    self.console.print("\n[red]Failed Command:[/red]")
                    self.console.print(f"Command: {failed_cmd.command}")
                    self.console.print(f"Error: {failed_cmd.error}")

        self.console.print(f"\n[bold green]Summary:[/bold green] {commands_data.summary}\n"+ 
                    (f"\nNote: {len(execution_result['failed_groups'])} groups had failures" 
                    if execution_result['failed_groups'] else ""))
        
        self.messages.append({
            "role": "assistant", 
            "content": f"Summary from TemplateAgent: {commands_data.summary}" + 
                    (f"\nNote: {len(execution_result['failed_groups'])} groups had failures" 
                    if execution_result['failed_groups'] else "")
        })

    
    def run(self,project_name: str,project_description: str) -> Iterator[RunResponse]:
        # Set up project directory
        project_dir = os.path.join(os.getcwd(), project_name.lower().replace(' ', '_'))
        self.executor.set_working_dir(project_dir)

        # --------------------------------------
        # STEP 1 : EXTRACT INFO FROM USER DESCRIPTION
        # --------------------------------------

        self.extractor.run(f"Project Name: {project_name}\nProject Description: {project_description}")
        
        extracted_content = self.extractor.memory.get_messages()[-1].get("content")

        # print("\nRaw extracted content: \n", extracted_content,"\n")

        # Define the regex pattern to match the project information section
        pattern = r'## Project Information Format.*?(?=TERMINATE)'
        match = re.search(pattern, extracted_content, re.DOTALL)

        if match:
            extracted_content = match.group(0).strip()
            print("\nProcessed extracted content: \n", extracted_content,"\n")
        else:
           print("No match found")

        self.messages.append({"role": "user", "content": extracted_content})

        # --------------------------------------
        # STEP 2 : STARTING AGENTIC WORKFLOW WITH THE TEMPLATE AGENT
        # --------------------------------------

        template_response = self.template_agent.run(extracted_content)
        
        commands_data: CommandResponse = template_response.content

        print("----------------------------------------")
                
        # for command in commands_data.commands:
        #     # yield RunResponse(
        #     #     event=RunEvent.ON_COMMAND,
        #     #     message=command.comment,
        #     #     data={
        #     #         "command": command.command,
        #     #         "comment": command.comment
        #     #     }
        #     # )
        #     self.console.print(f"[bold yellow]▶ Comment:[/bold yellow] {command.comment}")
        #     self.console.print(f"[bold cyan]$ Command:[/bold cyan] {command.command}")
        #     print("\n")

        # After getting template_response, add execution options
        self.console.print("\n[bold cyan]Command Execution Options:[/bold cyan]")
        self.console.print("1) Execute all commands")
        self.console.print("2) Execute step by step with confirmation")
        self.console.print("3) Save as script")
        
        while True:
            choice = input("\nEnter your choice (1-3): ")
            if choice in ['1', '2', '3']:
                break
            self.console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")

        mode_map = {
            '1': ExecutionMode.ALL,
            '2': ExecutionMode.STEP_BY_STEP,
            '3': ExecutionMode.SAVE_SCRIPT
        }
        
        self.execute_commands(commands_data, mode_map[choice], project_name)

        # self.console.print(f"\n[bold green]Summary:[/bold green] {commands_data.summary}\n")

        # self.messages.append({"role": "assistant", "content" : "Summary from TemplateAgent: " + commands_data.summary})

        return RunResponse(
            event = RunEvent.workflow_completed,
            message = "Workflow completed successfully",
        )
    
        # ----------------------------------------
        # STEP 3 : TESTER AGENT
        # ----------------------------------------

    
        tester_response = self.tester_agent.run(messages=self.messages)
        test_commands_data: CommandResponse = tester_response.content

        print("----------------------------------------")

        # for command in test_commands_data.commands:
        #     self.console.print(f"[bold yellow]▶ Comment:[/bold yellow] {command.comment}")
        #     self.console.print(f"[bold cyan]$ Command:[/bold cyan] {command.command}")
        #     print("\n")

        # After getting tester_response, add execution options
        self.console.print("\n[bold cyan]Command Execution Options:[/bold cyan]")
        self.console.print("1) Execute all commands")
        self.console.print("2) Execute step by step with confirmation")
        self.console.print("3) Save as script")
        
        while True:
            choice = input("\nEnter your choice (1-3): ")
            if choice in ['1', '2', '3']:
                break
            self.console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")

        mode_map = {
            '1': ExecutionMode.ALL,
            '2': ExecutionMode.STEP_BY_STEP,
            '3': ExecutionMode.SAVE_SCRIPT
        }
        
        self.execute_commands(test_commands_data, mode_map[choice], project_name)

        self.console.print(f"\n[bold green]Summary:[/bold green] {test_commands_data.summary}\n")

        