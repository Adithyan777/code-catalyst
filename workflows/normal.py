from enum import Enum
from phi.workflow import Workflow, RunResponse, RunEvent
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.utils.log import logger
from typing import Iterable, Iterator,List,Dict,Any,Optional
import time
from phi.utils.pprint import pprint_run_response
from pydantic import Field,BaseModel
import sys,os,subprocess
from phi.utils.timer import Timer
import json
from prompts.prompt_manager import PromptManager
from rich.console import Console

from utils import CommandExecutor, Command, CommandGroup, CommandResponse, ExecutionMode, FailedCommand, FailedGroup, GroupRecoveryPlan
from tools.ask_user import ask_human
import re
import questionary
from questionary import Choice

monitor_agents: bool = True
model_to_use : str = 'gpt-4o-mini-2024-07-18'

class NormalSetupWorkflow(Workflow):
    apikey: str = Field(...)
    console: Console = Field(...)
    executor: CommandExecutor = Field(None)
    messages : List[Dict[str, Any]] = Field(default_factory=list)

    extractor: Agent = Field(None)
    template_agent: Agent = Field(None)
    tester_agent: Agent = Field(None)
    recovery_agent: Agent = Field(None)
    
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
        
        # TODO: Modify system prompt and output model...
        self.recovery_agent = Agent(
            name="recovery_agent",
            model=OpenAIChat(model=model_to_use, api_key=self.apikey),
            system_prompt="""You are an expert at fixing failed command groups and understanding system errors. 
            You analyze failed commands within their group context to provide comprehensive solutions.
            
            When providing solutions:
            1. Analyze all failed commands in the group together
            2. Consider dependencies between commands
            3. Identify common root causes
            4. Provide solutions that maintain the group's objectives
            5. Consider the successful commands' context
            6. Ensure fixes maintain proper command order
            
            Return a structured plan with fixed commands and clear explanations.""",
            structured_outputs=True,
            output_model=GroupRecoveryPlan,
            monitoring=monitor_agents
        )

    def handle_failed_group(self, failed_group: FailedGroup, all_group_commands: List[Command]) -> bool:
        """
        Handles a failed group and attempts recovery. Returns True if fixed successfully.
        """
        input_context = {
            "group_info": {
                "name": failed_group.group_name,
                "description": failed_group.description
            },
            "failed_commands": [
                {
                    "command": fc.command,
                    "error": fc.error,
                    "output": fc.result.output
                }
                for fc in failed_group.failed_commands
            ],
            "group_commands": [
                {
                    "command": cmd.command,
                    "comment": cmd.comment
                }
                for cmd in all_group_commands
            ]
        }

        prompt = f"""
        I need help fixing a failed command group. Here's the context:

        Group Name: {failed_group.group_name}
        Group Description: {failed_group.description}

        Failed Commands and Their Errors:
        {json.dumps(input_context['failed_commands'], indent=2)}

        Full Group Context (All Commands):
        {json.dumps(input_context['group_commands'], indent=2)}

        Please analyze the errors and provide a recovery plan.
        """

        recovery_plan: GroupRecoveryPlan = self.recovery_agent.run(prompt).content

        self.console.print(f"\n[bold cyan]Recovery Analysis:[/bold cyan] {recovery_plan.analysis}")
        
        if recovery_plan.additional_instructions:
            self.console.print(f"\n[bold yellow]Additional Instructions:[/bold yellow]")
            self.console.print(recovery_plan.additional_instructions)
            
            proceed = questionary.confirm(
                "Proceed with fixes?",
                default=True
            ).ask()
            
            if not proceed:
                return False

        for fix in recovery_plan.fixed_commands:
            self.console.print(f"\n[bold yellow]Fixing Command:[/bold yellow]")
            self.console.print(f"Original: {fix.original_command}")
            self.console.print(f"Fixed: {fix.fixed_command}")
            self.console.print(f"Explanation: {fix.explanation}")
            
            result = self.executor.execute_command(fix.fixed_command, False)
            if result.success:
                self.console.print(f"[bold green]Fix successful![/bold green]")
            else:
                self.console.print(f"[bold red]Fix failed:[/bold red] {result.error}")
                return False
                

        return True

    def execute_commands(self, commands_data: CommandResponse, mode: ExecutionMode, project_name: str) -> None:
        if mode == ExecutionMode.SAVE_SCRIPT:
            script_path = self.executor.save_as_script(commands_data.groups, project_name)
            self.console.print(f"\n[bold green]Script saved as:[/bold green] {script_path}")
            return

        execution_result = self.executor.execute_command_groups(commands_data, mode)
        failed_groups: List[FailedGroup] = execution_result["failed_groups"]

        if failed_groups:
            self.console.print("\n[bold cyan]Starting recovery of Failed Groups...[/bold cyan]")
            
            # Analyze dependencies
            independent_groups = []
            dependent_groups = []
            
            for group in failed_groups:
                is_dependent = False
                for other_group in failed_groups:
                    if other_group.group_name in [g.depends_on for g in commands_data.groups if g.name == group.group_name]:
                        dependent_groups.append(group)
                        is_dependent = True
                        break
                if not is_dependent:
                    independent_groups.append(group)

            self.console.print(f"\n[bold yellow]Independent Failed Groups:[/bold yellow] {[g.group_name for g in independent_groups]}")
            self.console.print(f"[bold yellow]Dependent Failed Groups:[/bold yellow] {[g.group_name for g in dependent_groups]}")

            proceed = questionary.confirm(
                "Attempt to fix failed groups?",
                default=True
            ).ask()
            
            if not proceed:
                return

            # Fix independent groups first (could be parallel in theory)
            for group in independent_groups:
                group_commands = [cmd for g in commands_data.groups if g.name == group.group_name for cmd in g.commands]
                if not self.handle_failed_group(group, group_commands):
                    self.console.print(f"[bold red]Failed to fix group:[/bold red] {group.group_name}")

            # Fix dependent groups in order
            for group in dependent_groups:
                group_commands = [cmd for g in commands_data.groups if g.name == group.group_name for cmd in g.commands]
                if not self.handle_failed_group(group, group_commands):
                    self.console.print(f"[bold red]Failed to fix dependent group:[/bold red] {group.group_name}")
                    break

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

        # # After getting template_response, add execution options
        # self.console.print("\n[bold cyan]Command Execution Options:[/bold cyan]")
        # self.console.print("1) Execute all commands")
        # self.console.print("2) Execute step by step with confirmation")
        # self.console.print("3) Save as script")
        
        # self.console.print("\n")
        
        mode_choice = questionary.select(
            "Select execution mode:",
            choices=[
                Choice("Execute all commands", ExecutionMode.ALL),
                Choice("Execute step by step with confirmation", ExecutionMode.STEP_BY_STEP),
                Choice("Save as script", ExecutionMode.SAVE_SCRIPT)
            ],
        ).ask()
        
        if mode_choice:
            self.execute_commands(commands_data, mode_choice, project_name)
        else:
            self.console.print("[red]Execution cancelled[/red]")
            return

        self.console.print(f"\n[bold green]Summary:[/bold green] {commands_data.summary}\n")

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

