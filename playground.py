from prompts.prompt_manager import PromptManager

def main():
    prompt = PromptManager.get_prompt("extract_info_agent", setup="normal")
    info = PromptManager.get_template_info("extract_info_agent", setup="normal")
    print(prompt)
    print(info)

if __name__ == "__main__":
    main()