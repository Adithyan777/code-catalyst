from typing import Annotated
from rich.prompt import Prompt
from rich.console import Console

def ask_human(question: Annotated[str, "The question you want to ask the user about the missing info."]) -> Annotated[str, "Answer"]:
    """
    Function to prompt the user about the missing information in the user's description for Dockerfile generation.
    
    :param question: The question you want to ask the user about the missing info.
    :return: The answer provided by the user.
    """
    console = Console()
    
    # Use Rich to display the question and prompt for an answer
    answer = Prompt.ask(f"[bold green]Please answer the question:[/bold green] [yellow]{question}[/yellow]")
    
    # Return the provided answer
    return answer

# Example usage of the function:
# answer = ask_human("Do you have any port-configuration to be made?")
# print(f"The expert answered: {answer}")
