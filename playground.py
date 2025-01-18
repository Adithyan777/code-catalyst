from prompts.prompt_manager import PromptManager

def main():
    prompt = PromptManager.get_prompt("sample_prompt")
    info = PromptManager.get_template_info("sample_prompt")
    print(prompt)
    print(info)

if __name__ == "__main__":
    main()