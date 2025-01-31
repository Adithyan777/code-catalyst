def ask_human(question: str) -> str:
    """
    Function to ask the user follow-up questions to find the missing information in the user's description for their project..
    
    Args:
        question: The follow-up question you want to ask the user about the missing info.
    Returns:
        The answer provided by the user.
    """
    from rich.prompt import Prompt
    print(f"\nAgent needs information: {question}")
    response = Prompt.ask("Your response ")
    return response

    # Example usage of the function:
    # answer = ask_human("Do you have any port-configuration to be made?")
    # print(f"The expert answered: {answer}")