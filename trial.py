from enum import Enum
from phi.workflow import Workflow, RunResponse
from phi.agent import Agent
from phi.model.openai import OpenAIChat
from phi.utils.log import logger
from typing import Iterable, Iterator,Union
import time
from phi.utils.pprint import pprint_run_response
from pydantic import BaseModel
from phi.utils.timer import Timer
import json


# TODO:
    # 1. Figure out how to manage message history (control what goes to the LLM API) 
    # 2. Add response streaming and markdown support ✅
        # - The issue is as workflow.run() gives an Iterator[Response] which we capture using the for loop in the main method, but streaming also returns 
        #  an Iterator[Response] which gets discrete due to our for loop. So we need to differentiate and capture the Iterator[Response] from the streaming and use
        # it to display the messages in real-time.
    # 3. End workflow gracefully ✅
    # 4. Figure out how to dynamically give markdown support to streaming responses 
    # 5. Fifure out how to print non-streamed agent responses


# Custom events for better workflow tracking
class AgentEvent(str, Enum):
    HISTORIAN_THINKING = "HistorianThinking"
    HISTORIAN_RESPONSE = "HistorianResponse"
    FUTURIST_THINKING = "FuturistThinking"
    FUTURIST_RESPONSE = "FuturistResponse"
    MODERATOR_THINKING = "ModeratorThinking"
    MODERATOR_RESPONSE = "ModeratorResponse"

class WorkflowEvent(str, Enum):
    STARTED = "WorkflowStarted"
    IN_PROGRESS = "WorkflowInProgress"
    COMPLETED = "WorkflowCompleted"

class CustomWorkflow(Workflow):
    historian: Agent = Agent(
        name="Historian",
        role="Expert in world history",
        model=OpenAIChat(model="gpt-4o-mini"),
        instructions=[
            "You are a knowledgeable historian specializing in world history.",
            "Provide accurate historical information and context.",
            "Use formal language and cite historical periods when relevant."
        ]
    )

    futurist: Agent = Agent(
        name="Futurist",
        role="Visionary thinker about the future",
        model=OpenAIChat(model="gpt-4o-mini"),
        instructions=[
            "You are a forward-thinking futurist with innovative ideas.",
            "Speculate on future developments based on current trends.",
            "Use creative and optimistic language when discussing the future."
        ]
    )

    moderator: Agent = Agent(
        name="Moderator",
        role="Discussion facilitator",
        model=OpenAIChat(model="gpt-4o-mini"),
        instructions=[
            "You are a neutral moderator guiding the conversation.",
            "Ensure a balanced discussion between the historian and futurist.",
            "Summarize key points and ask thought-provoking questions."
        ]
    )

    def run(self) -> Iterator[RunResponse]:
        # Workflow start
        yield RunResponse(
            event=WorkflowEvent.STARTED.value,
            content="🔄 Initializing multi-agent analysis workflow..."
        )
        time.sleep(1)  # Brief pause for better UX

        # Historian phase
        yield RunResponse(
            event=AgentEvent.HISTORIAN_THINKING.value,
            content="📚 Consulting the Historian about World War II..."
        )
        yield from self.historian.run(
            "What were the main causes of World War II? Answer briefly.",
            stream=True
        )
        time.sleep(0.5)

        # Futurist phase
        yield RunResponse(
            event=AgentEvent.FUTURIST_THINKING.value,
            content="🔮 Asking the Futurist about 2050..."
        )
        
        # futuristic_response = self.futurist.run(
        #     "Based on current trends, what will be different in 2050?",
        # )
        # yield RunResponse(
        #     content=futuristic_response.content,
        #     event=AgentEvent.FUTURIST_RESPONSE.value
        # )

        yield from self.futurist.run(
            "Based on current trends, what will be different in 2050?",
        )
        time.sleep(0.5)

        # # Moderator summary
        # yield RunResponse(
        #     event=AgentEvent.MODERATOR_THINKING.value,
        #     content="⚖️ Moderator synthesizing perspectives..."
        # )

        # yield from self.moderator.run(
        #     """
        #     Synthesize these two perspectives:
        #     1. Historical perspective on WW2: {historian_response.content}
        #     2. Future vision for 2050: {futurist_response.content}
            
        #     Provide a brief, thoughtful synthesis connecting past and future.
        #     """,
        #     stream=True
        # )

        # Completion
        yield RunResponse(
            event=WorkflowEvent.COMPLETED.value,
            content="✨ Multi-agent analysis complete!"
        )

def custom_print_response(
    run_response: Union[RunResponse, Iterable[RunResponse]], 
    markdown: bool = False, 
    show_time: bool = False
) -> None:
    from rich.live import Live
    from rich.table import Table
    from rich.status import Status
    from rich.box import ROUNDED
    from rich.markdown import Markdown
    from rich.json import JSON
    from rich.console import Group
    from phi.cli.console import console

    event_list = [e.value for e in AgentEvent] + [e.value for e in WorkflowEvent]

    # Handle single response
    if isinstance(run_response, RunResponse):
        if run_response.event in event_list:
            event_message = ""
            if run_response.event == AgentEvent.HISTORIAN_THINKING.value:
                event_message = "\n📚 Historian is thinking..."
            elif run_response.event == AgentEvent.FUTURIST_THINKING.value:
                event_message = "\n🔮 Futurist is thinking..."
            elif run_response.event == AgentEvent.MODERATOR_THINKING.value:
                event_message = "\n⚖️ Moderator is synthesizing..."
            elif run_response.event == WorkflowEvent.STARTED.value:
                event_message = f"\n{'='*50}\n🌟 Starting Multi-Agent Analysis\n{'='*50}\n"
            elif run_response.event == WorkflowEvent.COMPLETED.value:
                event_message = f"\n\n{'='*50}\n✨ Analysis Complete!\n{'='*50}\n"
            elif run_response.event == AgentEvent.HISTORIAN_RESPONSE.value:
                event_message = "\n📚 Historian says:"
            elif run_response.event == AgentEvent.FUTURIST_RESPONSE.value:
                event_message = "\n🔮 Futurist says:"
            elif run_response.event == AgentEvent.MODERATOR_RESPONSE.value:
                event_message = "\n⚖️ Moderator says:"
            
            console.print(event_message)
            
            # For response events, also print the content
            if "RESPONSE" in run_response.event:
                table = Table(box=ROUNDED, border_style="blue", show_header=False)
                formatted_content = Markdown(run_response.content) if markdown else run_response.content
                table.add_row(formatted_content)
                console.print(table)
            return

        # Handle non-event single response
        single_response_content: Union[str, JSON, Markdown] = ""
        if isinstance(run_response.content, str):
            single_response_content = (
                Markdown(run_response.content) if markdown else run_response.get_content_as_string(indent=4)
            )
        elif isinstance(run_response.content, BaseModel):
            try:
                single_response_content = JSON(run_response.content.model_dump_json(exclude_none=True), indent=2)
            except Exception as e:
                logger.warning(f"Failed to convert response to Markdown: {e}")
                single_response_content = str(run_response.content)
        else:
            try:
                single_response_content = JSON(json.dumps(run_response.content), indent=4)
            except Exception as e:
                logger.warning(f"Failed to convert response to string: {e}")
                single_response_content = str(run_response.content)

        table = Table(box=ROUNDED, border_style="blue", show_header=False)
        table.add_row(single_response_content)
        console.print(table)
    
    # Handle streaming responses and iterables
    else:
        all_content = []  # Store all content including events
        streaming_response_content: str = ""
        
        with Live(console=console) as live_log:
            status = Status("Working...", spinner="dots")
            live_log.update(status)
            response_timer = Timer()
            response_timer.start()
            
            for resp in run_response:
                # Check if response has event first
                if hasattr(resp, 'event') and resp.event in event_list:
                    # Save current streaming content if any
                    if streaming_response_content:
                        table = Table(box=ROUNDED, border_style="blue", show_header=False)
                        formatted_response = Markdown(streaming_response_content) if markdown else streaming_response_content
                        table.add_row(formatted_response)
                        all_content.append(table)
                        streaming_response_content = ""

                    # Add event message
                    event_message = ""
                    if resp.event == AgentEvent.HISTORIAN_THINKING.value:
                        event_message = "\n📚 Historian is thinking..."
                    elif resp.event == AgentEvent.FUTURIST_THINKING.value:
                        event_message = "\n🔮 Futurist is thinking..."
                    elif resp.event == AgentEvent.MODERATOR_THINKING.value:
                        event_message = "\n⚖️ Moderator is synthesizing..."
                    elif resp.event == WorkflowEvent.STARTED.value:
                        event_message = f"\n{'='*50}\n🌟 Starting Multi-Agent Analysis\n{'='*50}\n"
                    elif resp.event == WorkflowEvent.COMPLETED.value:
                        event_message = f"\n\n{'='*50}\n✨ Analysis Complete!\n{'='*50}\n"
                    elif resp.event == AgentEvent.HISTORIAN_RESPONSE.value:
                        event_message = "\n📚 Historian says:"
                    elif resp.event == AgentEvent.FUTURIST_RESPONSE.value:
                        event_message = "\n🔮 Futurist says:"
                    elif resp.event == AgentEvent.MODERATOR_RESPONSE.value:
                        event_message = "\n⚖️ Moderator says:"
                    
                    all_content.append(event_message)
                    
                    # For response events, also display the content
                    if "RESPONSE" in resp.event and resp.content:
                        table = Table(box=ROUNDED, border_style="blue", show_header=False)
                        formatted_response = Markdown(resp.content) if markdown else resp.content
                        table.add_row(formatted_response)
                        all_content.append(table)
                    
                    live_log.update(Group(*all_content))
                    continue

                # Handle streaming content
                if isinstance(resp, RunResponse) and isinstance(resp.content, str):
                    streaming_response_content += resp.content

                    # Update display with all content
                    current_table = Table(box=ROUNDED, border_style="blue", show_header=False)
                    formatted_response = Markdown(streaming_response_content) if markdown else streaming_response_content
                    
                    if show_time:
                        current_table.add_row(f"Response\n({response_timer.elapsed:.1f}s)", formatted_response)
                    else:
                        current_table.add_row(formatted_response)

                    # Show all previous content plus current content
                    live_log.update(Group(*all_content, current_table))
                
            response_timer.stop()

if __name__ == "__main__":
    try:
        workflow = CustomWorkflow()
        run_responses = workflow.run()
        custom_print_response(run_responses, markdown=True, show_time=True)
    except KeyboardInterrupt:
        print("\n\n❌ Workflow interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error occurred: {str(e)}")
    finally:
        print("\n🎬 Session ended")
