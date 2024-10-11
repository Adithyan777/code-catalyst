from string import Template
import re
from sys_msg_docker import docker_team_intro
from sys_msg_normal import normal_team_intro
from rich.console import Console
from rich.prompt import Prompt

console = Console()

def extract_description(input_str):
    start_marker = "1."
    end_marker = "\nTERMINATE"
    
    start_index = input_str.find(start_marker)
    end_index = input_str.find(end_marker, start_index)

    if start_index == -1:
        return "Project Description NOT found in the LLM response."
    
    if end_index == -1:
        return input_str[start_index:]
    
    return input_str[start_index:end_index]

def extract_project_name(config_str: str) -> str:
    pattern = r"\*\*Project Name\*\*:\s*-\s*(.*)"
    match = re.search(pattern, config_str)
    if match:
        return match.group(1).strip()
    return ""
    
def get_sys_msg_docker(agent_msg:str):
    temp = Template(agent_msg)
    return temp.substitute(team_intro=docker_team_intro)

def get_sys_msg_normal(agent_msg:str):
    temp = Template(agent_msg)
    return temp.substitute(team_intro=normal_team_intro)

def extract_summary(text):
    # Define the regular expression pattern to match the summary
    pattern = r'(?i)summary.*?\n(.*)'
    
    # Use the re.search() function to find the match
    match = re.search(pattern, text, re.DOTALL)
    
    # If a match is found, return the summary text, otherwise return None
    if match:
        return match.group(1).strip()
    else:
        return None



