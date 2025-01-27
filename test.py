from phi.workflow import Workflow
from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.utils.log import logger
from phi.utils.pprint import pprint_run_response
from rich.prompt import Prompt
from typing import Iterator

# figuring out how to get user input within a workflow

def get_response_from_human(question: str) -> str:
    """Get a response from the human user for a question.
    
    Args: 
        question (str): The question to ask the human.

    Returns:
        str: The response from the human
    """
    response = input(f"\n🤔 {question}")
    return response

class CustomWorkflow(Workflow):
    agent: Agent = Agent(
        model=OpenAIChat(id="gpt-4o"),
        debug_mode=False,
        description="You are a quiz asssiatnt that asks the user questions on the football as well as correct them if they are wrong.",
        instructions="You can use the tool avaialble to ask the user questions and to get their resposne.",
        tools=[get_response_from_human],
        show_tool_calls=True,
        markdown=False,
        stream=True,
        monitoring=True
    )

    def run(self) -> Iterator[RunResponse]|None:
        logger.info("Starting the workflow")
        # exit_words = ["exit", "quit", "bye", "goodbye"]
        # while True:
        #     user_input = input("Your question: ")
        #     if user_input.lower() in exit_words:
        #         break
        #     response = self.agent.run(user_input)
        #     pprint_run_response(response)

        # response: Iterator[RunResponse] = self.agent.run("Lets start the quiz!",stream=True)
        # pprint_run_response(response, show_time=True)

        self.agent.print_response("Lets start the quiz!")
        logger.info("Ending the workflow")
        return
            

def main():
    workflow = CustomWorkflow()
    workflow.run()

if __name__ == "__main__":
    main()