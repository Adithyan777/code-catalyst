import os, sys, subprocess
from enum import Enum
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from rich.console import Console


class CommandType(Enum):
    SAFE = "safe"  # Read-only or informational commands
    SYSTEM = "system"  # Modifies system/environment
    DANGEROUS = "dangerous"  # Potentially destructive operations
    NETWORK = "network"  # Network-related operations

class Command(BaseModel):
    command: str = Field(
        ...,
        description="The command to execute"
    )
    comment: str = Field(
        ...,
        description="The comment associated with the command"
    )
    interactive: bool = Field(
        # default=False,
        description="Whether the command requires user interaction like y/n prompts, password prompt or any other input from user"
    )
    command_type: CommandType = Field(
        # default=CommandType.SAFE,
        description="Type of command for safety categorization"
    )

class CommandGroup(BaseModel):
    name: str = Field(..., description="Name of the command group")
    description: str = Field(..., description="Purpose of this group of commands")
    commands: List[Command] = Field(..., description="Commands in this group")
    depends_on: List[str] = Field(
        default_factory=list,
        description="Names of groups this group depends on"
    )

class CommandResponse(BaseModel):
    groups: List[CommandGroup] = Field(
        ...,
        description="List of command groups"
    )
    summary: str = Field(
        ...,
        description="Summary of the commands"
    )

class CommandResult(BaseModel):
    success: bool
    output: str
    error: str = ""

class ExecutionMode(Enum):
    ALL = "all"
    STEP_BY_STEP = "step"
    SAVE_SCRIPT = "save"

class FailedCommand(BaseModel):
    command: str = Field(..., description="The failed command")
    error: str = Field(..., description="Error message from the command")
    result: CommandResult = Field(..., description="Full command result")

class FailedGroup(BaseModel):
    group_name: str = Field(..., description="Name of the failed group")
    description: str = Field(..., description="Description of the failed group")
    failed_commands: List[FailedCommand] = Field(..., description="List of failed commands in this group")

class CommandExecutor:
    """
    A class to execute commands and command groups.
    """
    def __init__(self, console: Console):
        self.console = console
        self.working_dir = os.getcwd()
        self.group_results = {}
        # TODO: Add more commands to this list
        self.interactive_commands = [
            'npx create-react-app',
            'npm init',
            'pip install -e',
            'python setup.py',
            'yarn create',
            'create-next-app',
            'django-admin startproject',
        ]

    def set_working_dir(self, directory: str) -> None:
        """Set the working directory for command execution"""
        if os.path.exists(directory):
            self.working_dir = directory
            self.console.print(f"[bold blue]Working directory set to:[/bold blue] {directory}")
        else:
            os.makedirs(directory, exist_ok=True)
            self.working_dir = directory
            self.console.print(f"[bold blue]Created and set working directory to:[/bold blue] {directory}")

    def is_interactive_command(self, command: str) -> bool:
        """Check if the command is likely to be interactive"""
        return any(ic in command for ic in self.interactive_commands)

    def execute_command(self, command: str) -> CommandResult:
        """Execute a single command and return a CommandResult"""
        try:
            if self.is_interactive_command(command):
                self.console.print(f"\n[bold cyan]Running interactive command[/bold cyan]")
                
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=subprocess.PIPE if sys.platform == "win32" else None,
                    stdout=sys.stdout,
                    stderr=sys.stderr,
                    cwd=self.working_dir,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                
                return_code = process.wait()
                
                return CommandResult(
                    success=(return_code == 0),
                    output="Interactive command completed",
                    error="" if return_code == 0 else "Interactive command failed"
                )
            else:
                process = subprocess.run(
                    command,
                    shell=True,
                    text=True,
                    capture_output=True,
                    cwd=self.working_dir
                )
                
                return CommandResult(
                    success=(process.returncode == 0),
                    output=process.stdout,
                    error=process.stderr
                )

        except Exception as e:
            return CommandResult(
                success=False,
                output="",
                error=str(e)
            )

    def execute_group(self, group: CommandGroup, step_by_step: bool = False) -> Dict[str, CommandResult]:
        """Execute a single command group"""
        results = {}
        group_failed = False

        # Show group info and get confirmation if needed
        self.console.print("\n" + "="*50)
        self.console.print(f"[bold blue]Command Group:[/bold blue] {group.name}")
        self.console.print(f"[bold cyan]Description:[/bold cyan] {group.description}")
        self.console.print("="*50 + "\n")
        
        if step_by_step:
            response = input("Execute this group? (y/n): ").lower().strip()
            if not response.startswith('y'):
                return None  # Return None instead of empty dict to indicate skip

        for cmd in group.commands:
            if group_failed:
                results[cmd.command] = CommandResult(
                    success=False,
                    output="",
                    error="Skipped due to previous command failure in group"
                )
                continue

            # Command info with new format
            self.console.print(f"\n[bold yellow]Comment:[/bold yellow] {cmd.comment} [{cmd.command_type.value.upper()}]")
            self.console.print(f"[bold cyan]Command:[/bold cyan] {cmd.command}\n")

            result = self.execute_command(cmd.command)
            results[cmd.command] = result

            if result.success:
                self.console.print("[bold green]✓ Success[/bold green]")
                if result.output and result.output.strip():
                    self.console.print("[dim]Output:[/dim]")
                    self.console.print(f"[dim]{result.output.strip()}[/dim]")
            else:
                self.console.print("[bold red]✗ Error[/bold red]")
                if result.error:
                    self.console.print(f"[red]{result.error}[/red]")
                group_failed = True
            
            # Add separator between commands
            self.console.print("\n" + "-"*50)

        return results

    def execute_command_groups(self, command_response: CommandResponse, mode: ExecutionMode) -> Dict[str, Any]:
        """Execute all command groups in the correct order"""
        all_results = {}
        failed_groups = []
        executed_groups = set()
        remaining_groups = command_response.groups.copy()

        while remaining_groups:
            executable_groups = [
                group for group in remaining_groups
                if all(dep in executed_groups for dep in group.depends_on)
            ]

            if not executable_groups:
                self.console.print("[bold red]Error: Dependency cycle detected or all remaining groups have unmet dependencies[/bold red]")
                break

            current_group = executable_groups[0]  # Process one group at a time
            results = self.execute_group(
                current_group,
                step_by_step=(mode == ExecutionMode.STEP_BY_STEP)
            )
            
            if results is None:  # Group was skipped in step-by-step mode
                # Remove the group and continue to next iteration
                remaining_groups.remove(current_group)
                continue
                
            all_results[current_group.name] = results
            executed_groups.add(current_group.name)
            remaining_groups.remove(current_group)

            # Check for failed commands in this group
            failed_commands = []
            for cmd in current_group.commands:
                if cmd.command in results and not results[cmd.command].success:
                    failed_commands.append(
                        FailedCommand(
                            command=cmd.command,
                            error=results[cmd.command].error,
                            result=results[cmd.command]
                        )
                    )
            
            if failed_commands:
                failed_groups.append(
                    FailedGroup(
                        group_name=current_group.name,
                        description=current_group.description,
                        failed_commands=failed_commands
                    )
                )

        return {"results": all_results, "failed_groups": failed_groups}

    def save_as_script(self, groups: List[CommandGroup], project_name: str) -> str:
        """Save commands as a script file"""
        script_ext = ".sh" if sys.platform != "win32" else ".bat"
        script_name = f"{project_name.lower().replace(' ', '_')}_setup{script_ext}"
        script_path = os.path.join(self.working_dir, script_name)
        
        try:
            os.makedirs(self.working_dir, exist_ok=True)
            
            with open(script_path, "w") as f:
                if sys.platform != "win32":
                    f.write("#!/bin/bash\n\n")
                    f.write('set -e\n\n')  # Exit on error
                
                for group in groups:
                    f.write(f"# {'-'*50}\n")
                    f.write(f"# Group: {group.name}\n")
                    f.write(f"# Description: {group.description}\n")
                    f.write(f"# {'-'*50}\n\n")
                    
                    for cmd in group.commands:
                        f.write(f"# {cmd.comment}\n")
                        f.write(f"{cmd.command}\n\n")
            
            if sys.platform != "win32":
                os.chmod(script_path, 0o755)  # Make executable on Unix-like systems
            
            return script_path
            
        except Exception as e:
            self.console.print(f"[bold red]Error saving script:[/bold red] {str(e)}")
            return None
        

class CommandExecutorTrial:
    def __init__(self, console: Console):
        self.console = console
        self.working_dir = os.getcwd()
        self.group_results = {}

    def set_working_dir(self, directory: str) -> None:
        """Set the working directory for command execution"""
        if os.path.exists(directory):
            self.working_dir = directory
            self.console.print(f"[bold blue]Working directory set to:[/bold blue] {directory}")
        else:
            os.makedirs(directory, exist_ok=True)
            self.working_dir = directory
            self.console.print(f"[bold blue]Created and set working directory to:[/bold blue] {directory}")

    def execute_command(self, command: str) -> CommandResult:
        """Execute a command using interactive subprocess"""
        try:
            # Use Popen for all commands to handle potential interaction
            process = subprocess.Popen(
                command,
                shell=True,
                stdin=sys.stdin,  # Connect to terminal stdin
                stdout=subprocess.PIPE,  # Capture output but still show it
                stderr=subprocess.PIPE,
                cwd=self.working_dir,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Create output and error buffers
            output_buffer = []
            error_buffer = []

            # Use separate threads to read stdout and stderr to prevent blocking
            def read_output():
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        output_line = line.rstrip()
                        output_buffer.append(output_line)
                        self.console.print(f"[dim]{output_line}[/dim]")

            def read_error():
                while True:
                    line = process.stderr.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        error_line = line.rstrip()
                        error_buffer.append(error_line)
                        self.console.print(f"[red]{error_line}[/red]")

            # Start output reading threads
            import threading
            stdout_thread = threading.Thread(target=read_output)
            stderr_thread = threading.Thread(target=read_error)
            stdout_thread.start()
            stderr_thread.start()

            # Wait for the process to complete
            return_code = process.wait()

            # Wait for output threads to complete
            stdout_thread.join()
            stderr_thread.join()

            # Close file descriptors
            process.stdout.close()
            process.stderr.close()

            return CommandResult(
                success=(return_code == 0),
                output="\n".join(output_buffer),
                error="\n".join(error_buffer)
            )

        except Exception as e:
            return CommandResult(
                success=False,
                output="",
                error=str(e)
            )

    def execute_group(self, group: CommandGroup, step_by_step: bool = False) -> Dict[str, CommandResult]:
        """Execute a single command group"""
        results = {}
        group_failed = False

        # Show group info and get confirmation if needed
        self.console.print("\n" + "="*50)
        self.console.print(f"[bold blue]Command Group:[/bold blue] {group.name}")
        self.console.print(f"[bold cyan]Description:[/bold cyan] {group.description}")
        self.console.print("="*50 + "\n")
        
        if step_by_step:
            response = input("Execute this group? (y/n): ").lower().strip()
            if not response.startswith('y'):
                return None  # Return None instead of empty dict to indicate skip

        for cmd in group.commands:
            if group_failed:
                results[cmd.command] = CommandResult(
                    success=False,
                    output="",
                    error="Skipped due to previous command failure in group"
                )
                continue

            # Command info with new format
            self.console.print(f"\n[bold yellow]Comment:[/bold yellow] {cmd.comment} [{cmd.command_type.value.upper()}]")
            self.console.print(f"[bold cyan]Command:[/bold cyan] {cmd.command}\n")

            result = self.execute_command(cmd.command)
            results[cmd.command] = result

            if result.success:
                self.console.print("[bold green]✓ Success[/bold green]")
            else:
                self.console.print("[bold red]✗ Error[/bold red]")
                group_failed = True
            
            # Add separator between commands
            self.console.print("\n" + "-"*50)

        return results

    def execute_command_groups(self, command_response: CommandResponse, mode: ExecutionMode) -> Dict[str, Any]:
        """Execute all command groups in the correct order"""
        all_results = {}
        failed_groups = []
        executed_groups = set()
        remaining_groups = command_response.groups.copy()

        while remaining_groups:
            executable_groups = [
                group for group in remaining_groups
                if all(dep in executed_groups for dep in group.depends_on)
            ]

            if not executable_groups:
                self.console.print("[bold red]Error: Dependency cycle detected or all remaining groups have unmet dependencies[/bold red]")
                break

            current_group = executable_groups[0]  # Process one group at a time
            results = self.execute_group(
                current_group,
                step_by_step=(mode == ExecutionMode.STEP_BY_STEP)
            )
            
            if results is None:  # Group was skipped in step-by-step mode
                remaining_groups.remove(current_group)
                continue
                
            all_results[current_group.name] = results
            executed_groups.add(current_group.name)
            remaining_groups.remove(current_group)

            # Check for failed commands in this group
            failed_commands = []
            for cmd in current_group.commands:
                if cmd.command in results and not results[cmd.command].success:
                    failed_commands.append(
                        FailedCommand(
                            command=cmd.command,
                            error=results[cmd.command].error,
                            result=results[cmd.command]
                        )
                    )
            
            if failed_commands:
                failed_groups.append(
                    FailedGroup(
                        group_name=current_group.name,
                        description=current_group.description,
                        failed_commands=failed_commands
                    )
                )

        return {"results": all_results, "failed_groups": failed_groups}

    def save_as_script(self, groups: List[CommandGroup], project_name: str) -> str:
        """Save commands as a script file"""
        script_ext = ".sh" if sys.platform != "win32" else ".bat"
        script_name = f"{project_name.lower().replace(' ', '_')}_setup{script_ext}"
        script_path = os.path.join(self.working_dir, script_name)
        
        try:
            os.makedirs(self.working_dir, exist_ok=True)
            
            with open(script_path, "w") as f:
                if sys.platform != "win32":
                    f.write("#!/bin/bash\n\n")
                    f.write('set -e\n\n')  # Exit on error
                
                for group in groups:
                    f.write(f"# {'-'*50}\n")
                    f.write(f"# Group: {group.name}\n")
                    f.write(f"# Description: {group.description}\n")
                    f.write(f"# {'-'*50}\n\n")
                    
                    for cmd in group.commands:
                        f.write(f"# {cmd.comment}\n")
                        f.write(f"{cmd.command}\n\n")
            
            if sys.platform != "win32":
                os.chmod(script_path, 0o755)  # Make executable on Unix-like systems
            
            return script_path
            
        except Exception as e:
            self.console.print(f"[bold red]Error saving script:[/bold red] {str(e)}")
            return None