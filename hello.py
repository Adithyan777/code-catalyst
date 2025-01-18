from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.utils.pprint import pprint_run_response
from typing import Iterator
from phi.tools.shell import ShellTools


def main():
    print("Hello, world!")

    agent = Agent(
        model=OpenAIChat(id="gpt-4o-mini"),
        debug_mode=False,
        description="You are a helpful assistant that can answer questions and provide information.",
        instructions="Always answer briefly and informatively.",
        tools=[ShellTools()],
        show_tool_calls=True,
        markdown=False,
    )

    agent.cli_app()
    # response: Iterator[RunResponse] = agent.run("Show me the detailed contents of the current directory including the file/directory permissions, number of links, owner, group, file size, date modified, and the name of each file or directory",stream=True)
    # pprint_run_response(response, markdown=True, show_time=True)

if __name__ == "__main__":
    main()