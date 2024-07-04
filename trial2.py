from typing import Dict,List
from CustomGroupChat import CustomGroupChat,CustomGroupChatManager
from autogen import ConversableAgent,GroupChatManager
import os
import agentops
import json

# agentops.init()

# The Number Agent always returns the same numbers.
number_agent = ConversableAgent(
    name="Number_Agent",
    system_message="You return me the numbers I give you, one number each line.",
    llm_config={
        "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
        "cache_seed" : 45
    },
    human_input_mode="NEVER",
)

# The Adder Agent adds 1 to each number it receives.
adder_agent = ConversableAgent(
    name="Adder_Agent",
    system_message="You add 1 to each number I give you and return me the new numbers, one number each line.",
    llm_config={
        "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
        "cache_seed" : 45
    },
    human_input_mode="NEVER",
)

# The Multiplier Agent multiplies each number it receives by 2.
multiplier_agent = ConversableAgent(
    name="Multiplier_Agent",
    system_message="You multiply each number I give you by 2 and return me the new numbers, one number each line.",
    llm_config={
        "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
        "cache_seed" : 45
    },
    human_input_mode="NEVER",
)

# The Subtracter Agent subtracts 1 from each number it receives.
subtracter_agent = ConversableAgent(
    name="Subtracter_Agent",
    system_message="You subtract 1 from each number I give you and return me the new numbers, one number each line.",
    llm_config={
        "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
        "cache_seed" : 45
    },
    human_input_mode="NEVER",
)

# The Divider Agent divides each number it receives by 2.
divider_agent = ConversableAgent(
    name="Divider_Agent",
    system_message="You divide each number I give you by 2 and return me the new numbers, one number each line.",
    llm_config={
        "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
        "cache_seed" : 45
    },
    human_input_mode="NEVER",
)

adder_agent.description = "Add 1 to each input number."
multiplier_agent.description = "Multiply each input number by 2."
subtracter_agent.description = "Subtract 1 from each input number."
divider_agent.description = "Divide each input number by 2."
number_agent.description = "Return the numbers given."

def speaker_sel_func(lastspeaker:ConversableAgent,groupchat:CustomGroupChat):

    mess = groupchat.messages

    def clear_and_append(mess:List[Dict],last:int = 1):
        num = mess[-last:]
        mess.clear()
        mess.append(num)
        
    if lastspeaker is number_agent:
        clear_and_append(mess)
        return multiplier_agent,groupchat.messages
    elif lastspeaker is multiplier_agent:
        clear_and_append(mess)
        return subtracter_agent,groupchat.messages
    elif lastspeaker is subtracter_agent:
        clear_and_append(mess)
        return divider_agent,groupchat.messages
    elif lastspeaker is divider_agent:
        clear_and_append(mess)
        return adder_agent,groupchat.messages
    elif lastspeaker is adder_agent:
        if "5.5" not in mess[-1]["content"]:
            clear_and_append(mess)
            return adder_agent,groupchat.messages
        else:
            clear_and_append(mess)
            return None,None
            

group_chat = CustomGroupChat(
    agents=[adder_agent, multiplier_agent, subtracter_agent, divider_agent, number_agent],
    messages=[],
    select_speaker_auto_verbose=True,
    speaker_selection_method=speaker_sel_func
)

group_chat_manager = CustomGroupChatManager(
    groupchat = group_chat,
    llm_config={
        "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
        "cache_seed" : 45
    },
)

chat_result = number_agent.initiate_chat(
    group_chat_manager,
    message="3",
    silent=False
)
def print_defaultdict(defaultdict_obj):
    result = {"DefaultDict Contents": []}
    for agent, messages in defaultdict_obj.items():
        agent_dict = {"Agent": agent.name, "Messages": []}
        for message in messages:
            message_dict = {
                "Content": message.get('content', 'N/A'),
                "Role": message.get('role', 'N/A'),
                "Name": message.get('name', 'N/A')
            }
            agent_dict["Messages"].append(message_dict)
        result["DefaultDict Contents"].append(agent_dict)

    print(json.dumps(result, indent=4))

def print_agent_chat_history(chat_history):
    result = []
    for message in chat_history:
        message_dict = {
            "content": message.get('content', 'N/A'),
            "role": message.get('role', 'N/A')
        }
        if 'name' in message:
            message_dict["name"] = message["name"]
        result.append(message_dict)

    print(json.dumps(result, indent=4))

def print_chat_result(chat_result):
    print("ChatResult Contents:")
    print(f"Chat ID: {chat_result.chat_id}")
    print("Chat History:")
    for message in chat_result.chat_history:
        print(f"  - Content: {message['content']}")
        print(f"    Role: {message['role']}")
        if 'name' in message:
            print(f"    Name: {message['name']}")
    print(f"Summary: {chat_result.summary}")
    print("Cost:")
    for key, value in chat_result.cost.items():
        print(f"  {key}: {value}")
    print("Human Input:")
    for input_ in chat_result.human_input:
        print(f"  - {input_}")
    print("\n")

# print_chat_result(chat_result)
# print("group chat manager agent messages: ")
# print_defaultdict(group_chat_manager._oai_messages)
# print("number agent messages: ")
# print_defaultdict(number_agent._oai_messages)
print_defaultdict(group_chat_manager._oai_messages)
print("-------------------------------")
print(group_chat.messages)
# agentops.end_session("Success") 