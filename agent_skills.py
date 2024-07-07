from typing import Annotated
from rich.prompt import Prompt
from rich.console import Console
from pathlib import Path
import docker
from docker.errors import BuildError, APIError


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

def build_docker_image(image_name: str,path: str) -> Annotated[str,"Console data"]:
    """
    Function to build a Docker image from a Dockerfile.
    
    :param image_name: The name to assign to the built Docker image.
    :param path: relative path to the Dockerfile.
    """
    console = Console()
    client = docker.from_env()

    try:
        # Build the Docker image
        console.print(f"[bold green]Building Docker image '{image_name}'...[/bold green]")
        image, logs = client.images.build(path=path, tag=image_name)

        # Display build logs
        for log in logs:
            if 'stream' in log:
                console.print(log['stream'], end='')

        # Print success message
        console.print(f"[bold green]Docker image '{image_name}' built successfully.[/bold green]")
        return f"[bold green]Docker image '{image_name}' built successfully.[/bold green]"
    except BuildError as build_err:
        # Print build error message
        console.print(f"[bold red]Build failed: {build_err}[/bold red]")
        return f"[bold red]Build failed: {build_err}[/bold red]"
    except APIError as api_err:
        # Print API error message
        console.print(f"[bold red]Docker API error: {api_err}[/bold red]")
        return f"[bold red]Docker API error: {api_err}[/bold red]"
    except Exception as e:
        # Print general error message
        console.print(f"[bold red]An unexpected error occurred: {e}[/bold red]")
        return f"[bold red]An unexpected error occurred: {e}[/bold red]"

    # Example usage of the function:
    # build_docker_image("project_name")

