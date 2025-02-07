from rich.console import Console
from workflows.normal import NormalSetupWorkflow
import os
from dotenv import load_dotenv

load_dotenv()

apikey = os.getenv('OPENAI_API_KEY')
project_name = "todoApp"
project_description = "A simple todo app built using python with fastapi and django with NO other dependencies, special configurations or additional notes."

def main():
    workflow = NormalSetupWorkflow(console=Console(), apikey=apikey)
    respone = workflow.run(project_name,project_description)

if __name__ == '__main__':
    main()  