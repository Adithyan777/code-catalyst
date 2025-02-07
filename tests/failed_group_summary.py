import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import FailedGroup, FailedCommand, CommandResult
from typing import List

def print_failed_groups_summary(
    independent_groups: List[FailedGroup], dependent_groups: List[FailedGroup]
) -> None:
    """
    Prints a summary of failed groups.
    """
    total_failures = len(independent_groups) + len(dependent_groups)
    print("Failed Group Summary:")
    print(f"{total_failures} failures detected.\n")
    
    # Print independent failed groups
    print("┌─ Independent:")
    if independent_groups:
        for group in independent_groups:
            print(f"│  • {group.group_name}")
    else:
        print("│  (None)")
    
    # Print dependent failed groups
    print("└─ Dependent:")
    if dependent_groups:
        for group in dependent_groups:
            print(f"   • {group.group_name}")
    else:
        print("   (None)")

if __name__ == "__main__":
   if __name__ == "__main__":
    # Sample failed groups data
    independent = [
        FailedGroup(
            group_name="install-dependencies",
            description="Failure in installing dependencies",
            failed_commands=[
                FailedCommand(
                    command="pip install -r requirements.txt",
                    error="Timeout error",
                    result=CommandResult(success=False, output="", error="Timeout error")
                )
            ]
        ),
        FailedGroup(
            group_name="setup-django-project",
            description="Failure in setting up Django project",
            failed_commands=[
                FailedCommand(
                    command="django-admin startproject mysite",
                    error="Missing django package",
                    result=CommandResult(success=False, output="", error="Missing django package")
                )
            ]
        )
    ]
    dependent = []  # Example: no dependent failed groups

    # Print the summary of failed groups
    print_failed_groups_summary(independent, dependent)
    print("\n")