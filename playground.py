from prompts.prompt_manager import PromptManager

def main():
    prompt = PromptManager.get_prompt("compose_agent", setup="docker")
    info = PromptManager.get_template_info("compose_agent", setup="docker")
    print(prompt)
    print(info)

if __name__ == "__main__":
    main()