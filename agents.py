import os
from dotenv import load_dotenv
from autogen import UserProxyAgent
from autogen import AssistantAgent
from system_prompts import extract_info_agent
from agent_skills import ask_human

load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    raise ValueError("API key not found. Please set the API_KEY environment variable.")

llm_config = {
    "config_list": [{"model": "gpt-4o", "api_key": api_key }]
}


human_proxy = UserProxyAgent(
    "human_proxy",
    llm_config=False,  # no LLM used for human proxy
    human_input_mode="NEVER",  # always ask for human input
    # is_termination_msg = lambda msg: msg is not None and "TERMINATE" in msg.get("content", "")
)

extract_agent = AssistantAgent(
    "info_extracter",
    system_message=extract_info_agent,
    llm_config=llm_config,
    code_execution_config=False,  # Turn off code execution, by default it is off.
    function_map=None,  # No registered functions, by default it is None.
    human_input_mode="NEVER",  # Never ask for human input.
)

extract_agent.register_for_llm(name="ask_user",description="Asks user for the missing information")(ask_human)
human_proxy.register_for_execution(name="ask_user")(ask_human)


# Your code using the autogen library
def main():
    print(f"API_KEY SET!")
    result = human_proxy.initiate_chat(
        extract_agent, 
        silent=True,
        message="I am developing a web application called 'Chat App'. It's built using Python and requires Flask. The base image should be python:3.8.",
        )
    print(result.chat_history.content)

if __name__ == "__main__":
    main()
