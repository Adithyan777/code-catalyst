from enum import Enum
from phi.workflow import Workflow, RunResponse, RunEvent
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.utils.log import logger
from typing import Iterable, Iterator,List,Dict,Any
import time
from phi.utils.pprint import pprint_run_response
from pydantic import Field,BaseModel
from phi.utils.timer import Timer
import json
from prompts.prompt_manager import PromptManager
from rich.console import Console

from tools.ask_user import ask_human
import re

monitor_agents: bool = True

# Pydantic model for response from the agent
class CommandResponse(BaseModel):
    class Commands(BaseModel):
        command: str = Field(
            ...,
            description="The command to execute",
            example="npm init -y"
        )
        comment: str = Field(
            ...,
            description="The comment associated with the command",
            example="Initialize a new Node.js project"
        )

    
    commands: List[Commands] = Field(
        ...,
        description="List of commands for the team",
        example=[
            {
                "command": "npm init -y",
                "comment": "Initialize a new Node.js project"
            },
            {
                "command": "npm install express",
                "comment": "Install the Express.js framework"
            }
        ]
    )
    summary: str = Field(
        ...,
        description="Summary of the commands for the team",
        example="This set of commands initializes a new Node.js project and installs the Express.js framework."
    )

class NormalSetupWorkflow(Workflow):
    apikey: str = Field(...)
    console: Console = Field(...)
    extractor: Agent = Field(None)
    template_agent: Agent = Field(None)
    tester_agent: Agent = Field(None)
    messages : List[Dict[str, Any]] = Field(default_factory=list)
    
    def __init__(self, apikey: str, console: Console, **data):
        super().__init__(apikey=apikey, console=console, **data)
        # --------------------------------------
        # DEFINE AGENTS HERE (DO NOT FORGET TO ADD THEM ABOVE)
        # --------------------------------------
        self.extractor = Agent(
            name="extractor",
            model=OpenAIChat(model='gpt-4o-mini', api_key=self.apikey),
            system_prompt=PromptManager.get_prompt("extract_info_agent", setup="normal"),
            tools=[ask_human],
            monitoring=monitor_agents
        )

        self.template_agent = Agent(
            name="template_agent",
            model=OpenAIChat(model='gpt-4o-mini', api_key=self.apikey),
            system_prompt=PromptManager.get_prompt("template_agent", setup="normal"),
            structured_outputs=True,
            output_model=CommandResponse,
            monitoring=monitor_agents
        )

        self.tester_agent = Agent(
            name="tester_agent",
            model=OpenAIChat(model='gpt-4o-mini', api_key=self.apikey),
            system_prompt=PromptManager.get_prompt("tester_agent", setup="normal"),
            structured_outputs=True,
            output_model=CommandResponse,
            monitoring=monitor_agents
        )
    
    def run(self,project_name: str,project_description: str) -> Iterator[RunResponse]:

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
                
        for command in commands_data.commands:
            # yield RunResponse(
            #     event=RunEvent.ON_COMMAND,
            #     message=command.comment,
            #     data={
            #         "command": command.command,
            #         "comment": command.comment
            #     }
            # )
            self.console.print(f"[bold yellow]▶ Comment:[/bold yellow] {command.comment}")
            self.console.print(f"[bold cyan]$ Command:[/bold cyan] {command.command}")
            print("\n")

        self.console.print(f"\n[bold green]Summary:[/bold green] {commands_data.summary}\n")

        self.messages.append({"role": "assistant", "content" : "Summary from TemplateAgent: " + commands_data.summary})
    
        # ----------------------------------------
        # STEP 3 : TESTER AGENT
        # ----------------------------------------

        tester_response = self.tester_agent.run(messages=self.messages)
        test_commands_data: CommandResponse = tester_response.content

        print("----------------------------------------")

        for command in test_commands_data.commands:
            self.console.print(f"[bold yellow]▶ Comment:[/bold yellow] {command.comment}")
            self.console.print(f"[bold cyan]$ Command:[/bold cyan] {command.command}")
            print("\n")

        self.console.print(f"\n[bold green]Summary:[/bold green] {test_commands_data.summary}\n")

        return RunResponse(
            event = RunEvent.workflow_completed,
            message = "Workflow completed successfully",
        )