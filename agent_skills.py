from typing import Annotated,Tuple
from rich.prompt import Prompt
from rich.console import Console
from pathlib import Path
import docker
from docker.errors import BuildError, APIError
import os
import subprocess


def ask_human(question: Annotated[str, "The question you want to ask the user about the missing info."]) -> Annotated[str, "Answer"]:
    """
    Function to prompt the user about the missing information in the user's description for Dockerfile generation.
    
    :param question: The question you want to ask the user about the missing info.
    :return: The answer provided by the user.
    """
    
    # Use Rich to display the question and prompt for an answer
    answer = Prompt.ask(f"[bold green]Please answer the question:[/bold green] [yellow]{question}[/yellow]")
    
    # Return the provided answer
    return answer

    # Example usage of the function:
    # answer = ask_human("Do you have any port-configuration to be made?")
    # print(f"The expert answered: {answer}")

def write_to_file(filename: Annotated[str,"The filename in which you have to store the file with extension if any"], content: Annotated[str,"Content to be written to the file."]) -> Annotated[str,"Console data"]:
    """
    Function to write content to a file and save it on the machine.
    
    :param filename: The name of the file where the content will be written.
    :param content: The content to write to the file.
    """
    console = Console()

    try:
        # Create the file path
        file_path = Path(filename)
        
        # Write the content to the file
        with file_path.open(mode='w', encoding='utf-8') as file:
            file.write(content)
        
        # Print success message
        console.print(f"[bold green]Content successfully written to {file_path}[/bold green]")
        return f"[bold green]Content successfully written to {file_path}[/bold green]"
    except Exception as e:
        # Print error message
        console.print(f"[bold red]Failed to write to the file: {e}[/bold red]")
        return f"[bold red]Failed to write to the file: {e}[/bold red]"

    # Example usage of the function:
    # write_to_file("example.txt", "This is the content of the file.")

# todo - if working_dir of agent changes change here also
def run_docker_compose_up(
        project_dir:Annotated[str,"relative path to the project directory starting with './project_code' and ending with / eg: (./project_code/project_name/) "]
    ) -> Annotated[Tuple[str, int],"returns the error if any and the error code"]:
    """
    Run Docker Compose to build and start services.

    Args:
        project_dir (str): The directory containing the Docker Compose project.

    Returns:
        Tuple[str, int]: A tuple containing the output or error message and the error code.
    """
    try:
        os.chdir(project_dir)
    except FileNotFoundError as fnf_error:
        return str(fnf_error), 1  # Directory not found error

    commands = ["docker compose up", "docker-compose up"]
    
    for command in commands:
        try:
            result = subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return result.stdout.decode('utf-8')+"\nTERMINATE", 0  # Success
        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.decode('utf-8')
            if "command not found" in stderr_output:
                continue  # Try the next command
            else:
                return stderr_output, e.returncode  # Return error message and error code

    return "Error: Both 'docker compose up' and 'docker-compose up' failed", 1
    

def build_and_test_docker_image(
        project_dir:Annotated[str,"path to the project directory"],
        image_name:Annotated[str,"name of the Docker image to build"],
        container_name:Annotated[str,"name of the Docker container to run"],
        host_port:Annotated[str,"host port to map to the container port"],
        container_port:Annotated[str,"container port to map to the host port"],
        command:Annotated[str," full command to be executed which runs the test files generated"]
    )-> Annotated[str,"Output"]:
    """
    Function to build image and run tests inside the container.

    :param project_dir
    :param image_name
    :param container_name
    :param host_port 
    :param container_port
    :param command
    :return output
    """
    console = Console()
    client = docker.from_env()

    try:
        # Build the Docker image
        console.print(f"[bold green]Building the Docker image '{image_name}'...[/bold green]")
        image, build_logs = client.images.build(path=project_dir, tag=image_name)
        for log in build_logs:
            console.print(log.get('stream', '').strip())

        # Run the container
        console.print(f"[bold green]Running the container '{container_name}'...[/bold green]")
        container = client.containers.run(
            image=image_name,
            name=container_name,
            ports={f'{container_port}/tcp': host_port},
            detach=True
        )

        # Execute the tests inside the container
        console.print(f"[bold green]Running tests inside the container...[/bold green]")
        test_result = container.exec_run(command)
        console.print(test_result.output.decode())

        # Stop and remove the container
        console.print(f"[bold green]Stopping and removing the container '{container_name}'...[/bold green]")
        container.stop()
        container.remove()

        console.print("[bold green]Docker image built and tests executed successfully.[/bold green]")
        return "Docker image built and tests executed successfully.TERMINATE"

    except docker.errors.BuildError as build_err:
        console.print(f"[bold red]Error during image build: {build_err}[/bold red]")
        return f"Error during image build: {build_err}"
    except docker.errors.ContainerError as container_err:
        console.print(f"[bold red]Error during container execution: {container_err}[/bold red]")
        return f"Error during container execution: {container_err}"
    except docker.errors.DockerException as docker_err:
        console.print(f"[bold red]General Docker error: {docker_err}[/bold red]")
        return f"General Docker error: {docker_err}"
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        return f"An unexpected error occurred: {e}"

    # Example usage of the function:
    # build_and_test_docker_image("project_name","image_name","container_name","8080","8080","pytests tests")
