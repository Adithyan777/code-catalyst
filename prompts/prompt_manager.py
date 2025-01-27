from pathlib import Path
import frontmatter
from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateError, meta

class PromptManager:
    _env = None

    @classmethod
    def _get_env(cls,templates_dir="prompts/templates"):
        # Get the absolute path to the templates directory
        templates_dir = Path(__file__).parent.parent / templates_dir
        if cls._env is None:
            cls._env = Environment(
                loader=FileSystemLoader(str(templates_dir)),
                undefined=StrictUndefined
            )
        return cls._env

    @staticmethod
    def get_prompt(template, **kwargs):
        env = PromptManager._get_env()
        template_path = f"{template}.j2"
        with open(env.loader.get_source(env,template_path)[1]) as file:
            post = frontmatter.load(file)
        
        template = env.from_string(post.content)
        try:
            prompt = template.render(**kwargs)
            return prompt
        except TemplateError as e:
            raise ValueError(f"Error rendering template: {str(e)}")

    @staticmethod
    def get_template_info(template, **kwargs):
        env = PromptManager._get_env()
        template_path = f"{template}.j2"
        with open(env.loader.get_source(env,template_path)[1]) as file:
            post = frontmatter.load(file)
        
        ast = env.parse(post.content)
        variables = meta.find_undeclared_variables(ast)

        # Create template from description and render with kwargs
        description = post.metadata.get("description", "No description provided")
        description_template = env.from_string(description)
        try:
            rendered_description = description_template.render(**kwargs)
        except TemplateError:
            # Fallback to raw description if template rendering fails
            rendered_description = description

        return {
            "name": template,
            "description": rendered_description,
            "version": post.metadata.get("version", "No version provided"),
            "variables": list(variables),
        }