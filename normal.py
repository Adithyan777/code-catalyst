from pydantic import BaseModel
from openai import OpenAI,LengthFinishReasonError
from typing import List, Tuple
from pydantic import Field
from helper_functions import get_sys_msg_normal
from sys_msg_normal import template_agent_prompt
import json

client = OpenAI()

class CommandResponse(BaseModel):
    class Commands(BaseModel):
        command: str = Field(
            ...,
            description="The command to execute",
            example="npm init -y"
        )
        comment: str = Field(
            ...,
            description="The comment associated with the command",
            example="Initialize a new Node.js project"
        )

    
    commands: List[Commands] = Field(
        ...,
        description="List of commands for the team",
        example=[
            {
                "command": "npm init -y",
                "comment": "Initialize a new Node.js project"
            },
            {
                "command": "npm install express",
                "comment": "Install the Express.js framework"
            }
        ]
    )
    summary: str = Field(
        ...,
        description="Summary of the commands for the team",
        example="This set of commands initializes a new Node.js project and installs the Express.js framework."
    )

sysprompt = get_sys_msg_normal(template_agent_prompt)
final_response = None
json_response = {}


try:
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": sysprompt},
            {"role": "user", "content": "i want to setup a pthon venv."},
        ],
        response_format=CommandResponse,
    )
    response = completion.choices[0].message
    print(type(response.content))
    print(type(response.parsed))
    if response.parsed:
        # handle parsed response
        final_response = response.parsed
        json_response = final_response.model_dump_()
    elif response.refusal:
        # handle refusal
        print(response.refusal)
except Exception as e:
    # Handle edge cases
    if type(e) == LengthFinishReasonError:
        # Retry with a higher max tokens
        print("Too many tokens: ", e)
        pass
    else:
        # Handle other exceptions
        print(e)
        pass

# handling via JSON
print(type(json_response))
print(json_response)
print(json_response['commands'])
print(json_response['summary'])

# handling via pydantic model
# commands = final_response.commands
# summary = final_response.summary
# print(f"Summary: {summary}\n")
# for x in commands:
#     print(f"Command: {x.command}\nComment: {x.comment}\n")


