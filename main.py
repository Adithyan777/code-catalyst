import typer
import questionary
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
import json

from trial2 import initiate_multi_agents_normal
from trial import initiate_multi_agents_docker

APP_NAME = "code-catalyst"
CONFIG_DIR_PATH = Path(typer.get_app_dir(APP_NAME))
CONFIG_FILE_PATH = CONFIG_DIR_PATH / "config.json"
API_KEY_NAME = "API_KEY"

console = Console()
app = typer.Typer()

def show_welcome_message():
    welcome_message = """
    [bold cyan]:sparkles: Welcome to CodeCatalyst! :sparkles:[/bold cyan]
    
    [bold]Your ultimate tool for managing and interacting with your development environment.[/bold]

    :rocket: [green]Boost your productivity[/green] with streamlined workflows.
    :computer: [blue]Seamlessly integrate[/blue] with your favorite tools.
    :gear: [yellow]Automate[/yellow] tedious tasks and [mag_right]focus[/mag_right] on what matters.

    [bold]Let's get started![/bold] :tada:
    """
    console.print(Panel(welcome_message, expand=False))

def load_api_key():
    if CONFIG_FILE_PATH.is_file():
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
            return config.get(API_KEY_NAME)
    return None

def save_api_key(api_key):
    CONFIG_DIR_PATH.mkdir(parents=True, exist_ok=True)
    config = {}
    if CONFIG_FILE_PATH.is_file():
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
    config[API_KEY_NAME] = api_key
    with open(CONFIG_FILE_PATH, 'w') as f:
        json.dump(config, f, indent=4)

def prompt_with_validation(prompt_func, message, *args, **kwargs):
    while True:
        try:
            answer = prompt_func(message, *args, **kwargs).unsafe_ask()
            if answer:
                return answer
        except KeyboardInterrupt:
            raise typer.Abort()
            # console.print(Panel("[red]This question is mandatory. Please provide an answer.[/red]", expand=False))

def check_api_key():
    api_key = load_api_key()
    if not api_key:
        console.print(Panel("API key not found. Please enter your OpenAI API key", style="red", expand=False))
        api_key = prompt_with_validation(questionary.password, "Enter your OpenAI API key:")
        store_choice = questionary.confirm("Do you want to store this API key for future use?").ask()
        if store_choice:
            save_api_key(api_key)
            console.print(Panel("API key stored successfully.", style="green", expand=False))
        else:
            console.print(Panel("API key will be used for this session only.", style="yellow", expand=False))
    else:
        console.print(Panel("API key is already set.", style="green", expand=False))
    return api_key

def get_project_details():
    project_name = prompt_with_validation(questionary.text, "Enter your project name:")
    project_description = prompt_with_validation(questionary.text, "Enter your project description:")
    return project_name, project_description

def choose_dev_environment():
    dev_env = prompt_with_validation(questionary.select, "Choose the development environment you want to setup:", choices=["normal", "docker"])
    return dev_env

def initiate_chat():
    # Replace this with the actual function call to initiate chat with multi-agents
    console.print(Panel("Initiating chat with multi-agents...", style="cyan", expand=False))

@app.command()
def some_command():
    show_welcome_message()
    api_key = check_api_key()
    project_name, project_description = get_project_details()
    dev_env = choose_dev_environment()
    # console.print(Panel(f"Project Name: {project_name}", style="blue", expand=False))
    # console.print(Panel(f"Project Description: {project_description}", style="blue", expand=False))
    # console.print(Panel(f"Chosen Development Environment: {dev_env}", style="blue", expand=False))
    # Your functionality that requires the API key
    if(dev_env == "normal"):
        initiate_multi_agents_normal(api_key,project_name,project_description,console)
    else:
        initiate_multi_agents_docker(api_key,project_name,project_description,console)
    # console.print(f"Using API key: [bold]{api_key}[/bold]")

if __name__ == "__main__":
    app()
