from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.utils.pprint import pprint_run_response
from typing import Iterator


def main():
    print("Hello, world!")

    agent = Agent(
        model=OpenAIChat(id="gpt-3.5-turbo"),
        # debug_mode=True,
        description="You are a helpful assistant that can answer questions and provide information.",
        instructions="Always answer briefly and informatively.",
        markdown=False,
    )

    response: Iterator[RunResponse] = agent.run("Hi, What is quantum computing in simple terms? Explain in bulletpoints.",stream=True)
    pprint_run_response(response, markdown=True, show_time=True)

if __name__ == "__main__":
    main()