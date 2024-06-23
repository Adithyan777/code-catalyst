# main.py
import typer

app = typer.Typer()

@app.command()
def describe_project():
    """
    Ask the user for a description of their project.
    """
    description = typer.prompt("Please enter a description of your project")
    typer.echo(f"The description of your project is: {description}")

if __name__ == "__main__":
    app()
