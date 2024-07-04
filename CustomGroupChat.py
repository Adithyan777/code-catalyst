from autogen import GroupChat,Agent,ConversableAgent,GroupChatManager
from autogen.formatting_utils import colored
from autogen.exception_utils import NoEligibleSpeaker
from autogen.io.base import IOStream
from autogen.runtime_logging import log_new_agent,logging_enabled
from typing import Dict, List, Optional, Tuple, Union,Literal
from dataclasses import dataclass
import sys

@dataclass
class CustomGroupChat(GroupChat):
    input_plan: str = ""

    def __post_init__(self):
        super().__post_init__()
        # Additional validation or initialization for input_plan attribute
        if not isinstance(self.input_plan, str):
            raise ValueError("input_plan must be a string")

    def _auto_select_speaker(
        self,
        last_speaker: Agent,
        selector: ConversableAgent,
        messages: Optional[List[Dict]],
        agents: Optional[List[Agent]],
    ) -> Agent:
        """Selects next speaker for the "auto" speaker selection method. Utilises its own two-agent chat to determine the next speaker and supports requerying.

        Speaker selection for "auto" speaker selection method:
        1. Create a two-agent chat with a speaker selector agent and a speaker validator agent, like a nested chat
        2. Inject the group messages into the new chat
        3. Run the two-agent chat, evaluating the result of response from the speaker selector agent:
            - If a single agent is provided then we return it and finish. If not, we add an additional message to this nested chat in an attempt to guide the LLM to a single agent response
        4. Chat continues until a single agent is nominated or there are no more attempts left
        5. If we run out of turns and no single agent can be determined, the next speaker in the list of agents is returned

        Args:
            last_speaker Agent: The previous speaker in the group chat
            selector ConversableAgent:
            messages Optional[List[Dict]]: Current chat messages
            agents Optional[List[Agent]]: Valid list of agents for speaker selection

        Returns:
            Dict: a counter for mentioned agents.
        """

        # If no agents are passed in, assign all the group chat's agents
        if agents is None:
            agents = self.agents

        # The maximum number of speaker selection attempts (including requeries)
        # is the initial speaker selection attempt plus the maximum number of retries.
        # We track these and use them in the validation function as we can't
        # access the max_turns from within validate_speaker_name.
        max_attempts = 1 + self.max_retries_for_selecting_speaker
        attempts_left = max_attempts
        attempt = 0

        # Registered reply function for checking_agent, checks the result of the response for agent names
        def validate_speaker_name(recipient, messages, sender, config) -> Tuple[bool, Union[str, Dict, None]]:
            # The number of retries left, starting at max_retries_for_selecting_speaker
            nonlocal attempts_left
            nonlocal attempt

            attempt = attempt + 1
            attempts_left = attempts_left - 1

            return self._validate_speaker_name(recipient, messages, sender, config, attempts_left, attempt, agents)

        # Two-agent chat for speaker selection

        # Agent for checking the response from the speaker_select_agent
        checking_agent = ConversableAgent("checking_agent", default_auto_reply=max_attempts)

        # Register the speaker validation function with the checking agent
        checking_agent.register_reply(
            [ConversableAgent, None],
            reply_func=validate_speaker_name,  # Validate each response
            remove_other_reply_funcs=True,
        )

        # NOTE: Do we have a speaker prompt (select_speaker_prompt_template is not None)? If we don't, we need to feed in the last message to start the nested chat
        
        # Create a truncated list of the latest 3 group chat messages
        truncated_messages = messages[-1:] if messages else []  # <--- MODIFIED HERE

        # Agent for selecting a single agent name from the response
        speaker_selection_agent = ConversableAgent(
            "speaker_selection_agent",
            system_message=self.select_speaker_msg(agents),
            chat_messages=(
                {checking_agent: truncated_messages}
                if self.select_speaker_prompt_template is not None
                else {checking_agent: messages[:-1]}
            ),
            llm_config=selector.llm_config,
            human_input_mode="NEVER",  # Suppresses some extra terminal outputs, outputs will be handled by select_speaker_auto_verbose
        )

        # Create the starting message
        if self.select_speaker_prompt_template is not None:
            start_message = {
                "content": self.select_speaker_prompt(agents),
                "override_role": self.role_for_select_speaker_messages,
            }
        else:
            start_message = messages[-1]

        # Run the speaker selection chat
        result = checking_agent.initiate_chat(
            speaker_selection_agent,
            cache=None,  # don't use caching for the speaker selection chat
            message=start_message,
            max_turns=2
            * max(1, max_attempts),  # Limiting the chat to the number of attempts, including the initial one
            clear_history=False,
            silent=not self.select_speaker_auto_verbose,  # Base silence on the verbose attribute
        )

        return self._process_speaker_selection_result(result, last_speaker, agents)

    async def a_auto_select_speaker(
        self,
        last_speaker: Agent,
        selector: ConversableAgent,
        messages: Optional[List[Dict]],
        agents: Optional[List[Agent]],
    ) -> Agent:
        """(Asynchronous) Selects next speaker for the "auto" speaker selection method. Utilises its own two-agent chat to determine the next speaker and supports requerying.

        Speaker selection for "auto" speaker selection method:
        1. Create a two-agent chat with a speaker selector agent and a speaker validator agent, like a nested chat
        2. Inject the group messages into the new chat
        3. Run the two-agent chat, evaluating the result of response from the speaker selector agent:
            - If a single agent is provided then we return it and finish. If not, we add an additional message to this nested chat in an attempt to guide the LLM to a single agent response
        4. Chat continues until a single agent is nominated or there are no more attempts left
        5. If we run out of turns and no single agent can be determined, the next speaker in the list of agents is returned

        Args:
            last_speaker Agent: The previous speaker in the group chat
            selector ConversableAgent:
            messages Optional[List[Dict]]: Current chat messages
            agents Optional[List[Agent]]: Valid list of agents for speaker selection

        Returns:
            Dict: a counter for mentioned agents.
        """

        # If no agents are passed in, assign all the group chat's agents
        if agents is None:
            agents = self.agents

        # The maximum number of speaker selection attempts (including requeries)
        # We track these and use them in the validation function as we can't
        # access the max_turns from within validate_speaker_name
        max_attempts = 1 + self.max_retries_for_selecting_speaker
        attempts_left = max_attempts
        attempt = 0

        # Registered reply function for checking_agent, checks the result of the response for agent names
        def validate_speaker_name(recipient, messages, sender, config) -> Tuple[bool, Union[str, Dict, None]]:
            # The number of retries left, starting at max_retries_for_selecting_speaker
            nonlocal attempts_left
            nonlocal attempt

            attempt = attempt + 1
            attempts_left = attempts_left - 1

            return self._validate_speaker_name(recipient, messages, sender, config, attempts_left, attempt, agents)

        # Two-agent chat for speaker selection

        # Agent for checking the response from the speaker_select_agent
        checking_agent = ConversableAgent("checking_agent", default_auto_reply=max_attempts)

        # Register the speaker validation function with the checking agent
        checking_agent.register_reply(
            [ConversableAgent, None],
            reply_func=validate_speaker_name,  # Validate each response
            remove_other_reply_funcs=True,
        )

        # NOTE: Do we have a speaker prompt (select_speaker_prompt_template is not None)? If we don't, we need to feed in the last message to start the nested chat

        # Create a truncated list of the latest 3 group chat messages
        truncated_messages = messages[-1:] if messages else []
        print("Reached here")

        # Agent for selecting a single agent name from the response
        speaker_selection_agent = ConversableAgent(
            "speaker_selection_agent",
            system_message=self.select_speaker_msg(agents),
            chat_messages={checking_agent: truncated_messages},
            llm_config=selector.llm_config,
            human_input_mode="NEVER",  # Suppresses some extra terminal outputs, outputs will be handled by select_speaker_auto_verbose
        )

        # Create the starting message
        if self.select_speaker_prompt_template is not None:
            start_message = {
                "content": self.select_speaker_prompt(agents),
                "override_role": self.role_for_select_speaker_messages,
            }
        else:
            start_message = messages[-1]

        # Run the speaker selection chat
        result = await checking_agent.a_initiate_chat(
            speaker_selection_agent,
            cache=None,  # don't use caching for the speaker selection chat
            message=start_message,
            max_turns=2
            * max(1, max_attempts),  # Limiting the chat to the number of attempts, including the initial one
            clear_history=False,
            silent=not self.select_speaker_auto_verbose,  # Base silence on the verbose attribute
        )

        return self._process_speaker_selection_result(result, last_speaker, agents)
    
    def select_speaker_msg(self, agents: Optional[List[Agent]] = None) -> str:
        """Return the system message for selecting the next speaker. This is always the *first* message in the context."""
        if agents is None:
            agents = self.agents

        roles = self._participant_roles(agents)
        # agentlist = f"{[agent.name for agent in agents]}"
        plan = self.input_plan

        return_msg = self.select_speaker_message_template.format(roles=roles, plan=plan)
        return return_msg

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
                if agent != speaker:
                    self.send(message, agent, request_reply=False, silent=True)
            if self._is_termination_msg(message) or i == groupchat.max_round - 1:
                # The conversation is over or it's the last round
                break
            try:
                # select the next speaker
                speaker = groupchat.select_speaker(speaker, self)
                modified_message = [self._oai_messages[speaker][0], self._oai_messages[speaker][-1]]
                if self._oai_messages[speaker][0] == self._oai_messages[speaker][-1]:
                    modified_message = [self._oai_messages[speaker][0]]
                if not silent:
                    iostream = IOStream.get_default()
                    iostream.print(colored(f"\nNext speaker: {speaker.name}\n", "green"), flush=True)
                    # iostream.print(colored(f"{modified_message}"))
                # let the speaker speak
                reply = speaker.generate_reply(sender=self,messages=modified_message) 
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
    
    async def a_run_chat(
        self,
        messages: Optional[List[Dict]] = None,
        sender: Optional[Agent] = None,
        config: Optional[GroupChat] = None,
    ):
        """Run a group chat asynchronously."""
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
                await self.a_send(intro, agent, request_reply=False, silent=True)
            # NOTE: We do not also append to groupchat.messages,
            # since groupchat handles its own introductions

        if self.client_cache is not None:
            for a in groupchat.agents:
                a.previous_cache = a.client_cache
                a.client_cache = self.client_cache
        for i in range(groupchat.max_round):
            groupchat.append(message, speaker)

            if self._is_termination_msg(message):
                # The conversation is over
                break

            # broadcast the message to all agents except the speaker
            for agent in groupchat.agents:
                if agent != speaker:
                    await self.a_send(message, agent, request_reply=False, silent=True)
            if i == groupchat.max_round - 1:
                # the last round
                break
            try:
                # select the next speaker
                speaker = await groupchat.a_select_speaker(speaker, self)
                # let the speaker speak
                modified_message = [self._oai_messages[speaker][0],self._oai_messages[speaker][-1]] # <----------- MODIFY HERE
                print("Reached Here")
                reply = await speaker.a_generate_reply(sender=self,messages=modified_message)
            except KeyboardInterrupt:
                # let the admin agent speak if interrupted
                if groupchat.admin_name in groupchat.agent_names:
                    # admin agent is one of the participants
                    speaker = groupchat.agent_by_name(groupchat.admin_name)
                    reply = await speaker.a_generate_reply(sender=self)
                else:
                    # admin agent is not found in the participants
                    raise
            if reply is None:
                break
            # The speaker sends the message without requesting a reply
            await speaker.a_send(reply, self, request_reply=False, silent=silent)
            message = self.last_message(speaker)
        if self.client_cache is not None:
            for a in groupchat.agents:
                a.client_cache = a.previous_cache
                a.previous_cache = None
        return True, None

