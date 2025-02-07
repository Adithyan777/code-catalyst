import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import CommandResponse, load_json_as_model


def print_command_summary(response: CommandResponse) -> None:
    """
    Prints a command summary in the CLI.
    """
    groups = response.groups
    num_groups = len(groups)
    
    print("Command Execution")
    print(f"{num_groups} command groups detected.\n")
    
    for i, group in enumerate(groups):
        # Choose the correct prefix based on the group's position.
        if i == 0:
            group_prefix = "┌"
        elif i == num_groups - 1:
            group_prefix = "└"
        else:
            group_prefix = "├"
        
        # Print the group header.
        print(f"{group_prefix}─ {group.name}:")
        
        # Use a vertical line indent for all groups except the last.
        # For the last group, use a plain space indent.
        command_indent = "   " if i == num_groups - 1 else "│  "
        for cmd in group.commands:
            print(f"{command_indent}• {cmd.comment}")


if __name__ == "__main__":
    response = load_json_as_model('commands_data.json', CommandResponse)
    print_command_summary(response)
    print("\n")