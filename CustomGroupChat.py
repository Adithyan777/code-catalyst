from autogen import GroupChat,Agent,ConversableAgent,GroupChatManager
from autogen.formatting_utils import colored
from autogen.exception_utils import NoEligibleSpeaker
from autogen.io.base import IOStream
from autogen.runtime_logging import log_new_agent,logging_enabled
from typing import Dict, List, Optional, Tuple, Union,Literal,Callable
from dataclasses import dataclass
import sys
import logging

logger = logging.getLogger(__name__)

@dataclass
class CustomGroupChat(GroupChat):

    def __post_init__(self):
        super().__post_init__()

    def _prepare_and_select_agents(
        self,
        last_speaker: Agent,
    ) -> Tuple[Optional[Agent], List[Agent], Optional[List[Dict]]]:
        # If self.speaker_selection_method is a callable, call it to get the next speaker.
        # If self.speaker_selection_method is a string, return it.
        speaker_selection_method = self.speaker_selection_method
        if isinstance(self.speaker_selection_method, Callable):
            result = self.speaker_selection_method(last_speaker, self)            # MODIFIED - accepting the message from custom speaker_selection_method
            if result is not None:                                                
                selected_agent, send_msg = result                                  # MODIFIED - unpacking return value from custom speaker_selection_method if its not None
            else:
                # Handle the case where speaker_selection_method returns None
                selected_agent = None
            if selected_agent is None:
                raise NoEligibleSpeaker("Custom speaker selection function returned None. Terminating conversation.")
            elif isinstance(selected_agent, Agent):
                if selected_agent in self.agents:
                    return selected_agent, self.agents, send_msg                          # MODIFIED - accepting the message from custom speaker_selection_method
                else:
                    raise ValueError(
                        f"Custom speaker selection function returned an agent {selected_agent.name} not in the group chat."
                    )
            elif isinstance(selected_agent, str):
                # If returned a string, assume it is a speaker selection method
                speaker_selection_method = selected_agent
            else:
                raise ValueError(
                    f"Custom speaker selection function returned an object of type {type(selected_agent)} instead of Agent or str."
                )

        if speaker_selection_method.lower() not in self._VALID_SPEAKER_SELECTION_METHODS:
            raise ValueError(
                f"GroupChat speaker_selection_method is set to '{speaker_selection_method}'. "
                f"It should be one of {self._VALID_SPEAKER_SELECTION_METHODS} (case insensitive). "
            )

        # If provided a list, make sure the agent is in the list
        allow_repeat_speaker = (
            self.allow_repeat_speaker
            if isinstance(self.allow_repeat_speaker, bool) or self.allow_repeat_speaker is None
            else last_speaker in self.allow_repeat_speaker
        )

        agents = self.agents
        n_agents = len(agents)
        # Warn if GroupChat is underpopulated
        if n_agents < 2:
            raise ValueError(
                f"GroupChat is underpopulated with {n_agents} agents. "
                "Please add more agents to the GroupChat or use direct communication instead."
            )
        elif n_agents == 2 and speaker_selection_method.lower() != "round_robin" and allow_repeat_speaker:
            logger.warning(
                f"GroupChat is underpopulated with {n_agents} agents. "
                "Consider setting speaker_selection_method to 'round_robin' or allow_repeat_speaker to False, "
                "or use direct communication, unless repeated speaker is desired."
            )

        if (
            self.func_call_filter
            and self.messages
            and ("function_call" in self.messages[-1] or "tool_calls" in self.messages[-1])
        ):
            funcs = []
            if "function_call" in self.messages[-1]:
                funcs += [self.messages[-1]["function_call"]["name"]]
            if "tool_calls" in self.messages[-1]:
                funcs += [
                    tool["function"]["name"] for tool in self.messages[-1]["tool_calls"] if tool["type"] == "function"
                ]

            # find agents with the right function_map which contains the function name
            agents = [agent for agent in self.agents if agent.can_execute_function(funcs)]
            if len(agents) == 1:
                # only one agent can execute the function
                return agents[0], agents, None
            elif not agents:
                # find all the agents with function_map
                agents = [agent for agent in self.agents if agent.function_map]
                if len(agents) == 1:
                    return agents[0], agents, None
                elif not agents:
                    raise ValueError(
                        f"No agent can execute the function {', '.join(funcs)}. "
                        "Please check the function_map of the agents."
                    )
        # remove the last speaker from the list to avoid selecting the same speaker if allow_repeat_speaker is False
        agents = [agent for agent in agents if agent != last_speaker] if allow_repeat_speaker is False else agents

        # Filter agents with allowed_speaker_transitions_dict

        is_last_speaker_in_group = last_speaker in self.agents

        # this condition means last_speaker is a sink in the graph, then no agents are eligible
        if last_speaker not in self.allowed_speaker_transitions_dict and is_last_speaker_in_group:
            raise NoEligibleSpeaker(f"Last speaker {last_speaker.name} is not in the allowed_speaker_transitions_dict.")
        # last_speaker is not in the group, so all agents are eligible
        elif last_speaker not in self.allowed_speaker_transitions_dict and not is_last_speaker_in_group:
            graph_eligible_agents = []
        else:
            # Extract agent names from the list of agents
            graph_eligible_agents = [
                agent for agent in agents if agent in self.allowed_speaker_transitions_dict[last_speaker]
            ]

        # If there is only one eligible agent, just return it to avoid the speaker selection prompt
        if len(graph_eligible_agents) == 1:
            return graph_eligible_agents[0], graph_eligible_agents, None

        # If there are no eligible agents, return None, which means all agents will be taken into consideration in the next step
        if len(graph_eligible_agents) == 0:
            graph_eligible_agents = None

        # Use the selected speaker selection method
        select_speaker_messages = None
        if speaker_selection_method.lower() == "manual":
            selected_agent = self.manual_select_speaker(graph_eligible_agents)
        elif speaker_selection_method.lower() == "round_robin":
            selected_agent = self.next_agent(last_speaker, graph_eligible_agents)
        elif speaker_selection_method.lower() == "random":
            selected_agent = self.random_select_speaker(graph_eligible_agents)
        else:  # auto
            selected_agent = None
            select_speaker_messages = self.messages.copy()
            # If last message is a tool call or function call, blank the call so the api doesn't throw
            if select_speaker_messages[-1].get("function_call", False):
                select_speaker_messages[-1] = dict(select_speaker_messages[-1], function_call=None)
            if select_speaker_messages[-1].get("tool_calls", False):
                select_speaker_messages[-1] = dict(select_speaker_messages[-1], tool_calls=None)
        return selected_agent, graph_eligible_agents, select_speaker_messages
    
    def select_speaker(self, last_speaker: Agent, selector: ConversableAgent) -> Agent:
        """Select the next speaker (with requery)."""

        # Prepare the list of available agents and select an agent if selection method allows (non-auto)
        selected_agent, agents, messages = self._prepare_and_select_agents(last_speaker)    
        if selected_agent:
            return selected_agent,messages                              # MODIFIED - returning the message from custom speaker_selection_method to run_chat of chat_manager_agent
        elif self.speaker_selection_method == "manual":
            # An agent has not been selected while in manual mode, so move to the next agent
            return self.next_agent(last_speaker)

        # auto speaker selection with 2-agent chat
        return self._auto_select_speaker(last_speaker, selector, messages, agents)


    
class CustomGroupChatManager(GroupChatManager):

    def __init__(
        self,
        groupchat: GroupChat,
        name: Optional[str] = "chat_manager",
        # unlimited consecutive auto reply by default
        max_consecutive_auto_reply: Optional[int] = sys.maxsize,
        human_input_mode: Literal["ALWAYS", "NEVER", "TERMINATE"] = "NEVER",
        system_message: Optional[Union[str, List]] = "Group chat manager.",
        silent: bool = False,
        **kwargs,
    ):
        if (
            kwargs.get("llm_config")
            and isinstance(kwargs["llm_config"], dict)
            and (kwargs["llm_config"].get("functions") or kwargs["llm_config"].get("tools"))
        ):
            raise ValueError(
                "GroupChatManager is not allowed to make function/tool calls. Please remove the 'functions' or 'tools' config in 'llm_config' you passed in."
            )

        super().__init__(
            groupchat=groupchat,
            name=name,
            max_consecutive_auto_reply=max_consecutive_auto_reply,
            human_input_mode=human_input_mode,
            system_message=system_message,
            silent=silent,
            **kwargs,
        )
        if logging_enabled():
            log_new_agent(self, locals())
        # Store groupchat
        self._groupchat = groupchat

        self._silent = silent

        # Order of register_reply is important.
        # Allow sync chat if initiated using initiate_chat
        self.register_reply(Agent, CustomGroupChatManager.run_chat, config=groupchat, reset_config=GroupChat.reset)
        # Allow async chat if initiated using a_initiate_chat
        self.register_reply(
            Agent,
            CustomGroupChatManager.a_run_chat,
            config=groupchat,
            reset_config=GroupChat.reset,
            ignore_async_in_sync_chat=True,
        )

    def run_chat(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[GroupChat] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Run a group chat."""
        if messages is None:
            messages = self._oai_messages[sender]
        message = messages[-1]
        speaker = sender
        groupchat = config
        send_introductions = getattr(groupchat, "send_introductions", False)
        silent = getattr(self, "_silent", False)

        if send_introductions:
            # Broadcast the intro
            intro = groupchat.introductions_msg()
            for agent in groupchat.agents:
                self.send(intro, agent, request_reply=False, silent=True)
            # NOTE: We do not also append to groupchat.messages,
            # since groupchat handles its own introductions

        if self.client_cache is not None:
            for a in groupchat.agents:
                a.previous_cache = a.client_cache
                a.client_cache = self.client_cache
        for i in range(groupchat.max_round):
            groupchat.append(message, speaker)
            # broadcast the message to all agents except the speaker
            for agent in groupchat.agents:                                 
                if agent != speaker and i == 0:                        # MODIFIED : broadcast only the first message of the groupChat otherwise its causing an error in ConversableAgent.
                    self.send(message, agent, request_reply=False, silent=True)
            if self._is_termination_msg(message) or i == groupchat.max_round - 1:
                # The conversation is over or it's the last round
                break
            try:
                # select the next speaker
                speaker , send_msg = groupchat.select_speaker(speaker, self)             # MODIFIED - accepting the message from custom speaker_selection_method
                if not silent:
                    iostream = IOStream.get_default()
                    iostream.print(colored(f"\nNext speaker: {speaker.name}\n", "green"), flush=True)
                # let the speaker speak
                reply = speaker.generate_reply(sender=self,messages=send_msg)              # MODIFIED - sending the message from custom speaker_selection_method to generate_reply of speaker_agent.
            except KeyboardInterrupt:
                # let the admin agent speak if interrupted
                if groupchat.admin_name in groupchat.agent_names:
                    # admin agent is one of the participants
                    speaker = groupchat.agent_by_name(groupchat.admin_name)
                    reply = speaker.generate_reply(sender=self)
                else:
                    # admin agent is not found in the participants
                    raise
            except NoEligibleSpeaker:
                # No eligible speaker, terminate the conversation
                break

            if reply is None:
                # no reply is generated, exit the chat
                break

            # check for "clear history" phrase in reply and activate clear history function if found
            if (
                groupchat.enable_clear_history
                and isinstance(reply, dict)
                and reply["content"]
                and "CLEAR HISTORY" in reply["content"].upper()
            ):
                reply["content"] = self.clear_agents_history(reply, groupchat)

            # The speaker sends the message without requesting a reply
            speaker.send(reply, self, request_reply=False, silent=silent)
            message = self.last_message(speaker)
        if self.client_cache is not None:
            for a in groupchat.agents:
                a.client_cache = a.previous_cache
                a.previous_cache = None
        return True, None