from prompts.prompt_manager import PromptManager
from utils import CommandExecutor,CommandResult
from rich.console import Console

def main():
    console = Console()
    executor = CommandExecutor(console)
    result = executor.execute_command("cd next && ls",False)
    
    print("\n\n\n-----------------------------------\n\n\n")
    print(result)
    

if __name__ == "__main__":
    main()