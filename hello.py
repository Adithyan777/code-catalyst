from phi.agent import Agent, RunResponse
from phi.model.openai import OpenAIChat
from phi.utils.pprint import pprint_run_response
from typing import Iterator
from phi.tools.shell import ShellTools
from pprint import pprint

# figuring out how to modify chat message history

def main():
    
    agent = Agent(
        model=OpenAIChat(id="gpt-4o-mini"),
        debug_mode=False,
        description="You are a helpful assistant that can answer questions and provide information.",
        instructions="Always answer briefly and informatively.",
        tools=[ShellTools()],
        show_tool_calls=True,
        markdown=False,
        monitoring=True
    )

    
    agent.print_response("Hi whats 2+2?")
    agent.print_response("Hi my name is Ronaldo...")

    print('Agent get messages')
    pprint(agent.memory.get_messages())

    print('Agent get message pairs')
    history = agent.memory.get_message_pairs() #  <--- IMP:  From this we can get chat history in the form of Messages object and use it to add to agent history
    # pprint(history)

    messages_to_add = [msg for tuple_pair in history for msg in tuple_pair]
    pprint(messages_to_add[-2:])

    agent2 = Agent(
        model=OpenAIChat(id="gpt-4o-mini"),
        debug_mode=False,
        description="You are a helpful assistant that can answer questions and provide information.",
        instructions="Always answer briefly and informatively.",
        add_chat_history_to_messages=True,
        monitoring=True
    )
    agent2.memory.add_messages(messages_to_add[-2:])
    agent2.print_response('Hi again')
    # agent2.cli_app()
    # print("------------------------------------------------")
    print('Agent2 get messages')
    pprint(agent2.memory.get_messages())
    print('Agent2 get message pairs')
    history = agent2.memory.get_message_pairs() #  <--- IMP:  From this we can get chat history in the form of Messages object and use it to add to agent history
    # pprint(history)  
    messages_to_add = [msg for tuple_pair in history for msg in tuple_pair]
    pprint(messages_to_add)
    
    # response: Iterator[RunResponse] = agent.run("Show me the detailed contents of the current directory including the file/directory permissions, number of links, owner, group, file size, date modified, and the name of each file or directory",stream=True)
    # pprint_run_response(response, markdown=True, show_time=True)

if __name__ == "__main__":
    main()