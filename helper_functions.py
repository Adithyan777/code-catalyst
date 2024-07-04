def extract_prompt(input_str):
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
    import re
    pattern = r"\*\*Project Name\*\*:\s*-\s*(.*)"
    match = re.search(pattern, config_str)
    if match:
        return match.group(1).strip()
    return ""
    