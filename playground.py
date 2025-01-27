from prompts.prompt_manager import PromptManager

def main():
    # prompt = PromptManager.get_prompt("extract_info_agent", setup="docker")
    info = PromptManager.get_template_info("extract_info_agent", setup="docker")
    # print(prompt)
    print(info.get("description"))

if __name__ == "__main__":
    main()