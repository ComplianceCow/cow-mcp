import os

from mcpconfig.config import mcp


@mcp.prompt()
def ccow_workflow_knowledge() -> str:

    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "workflow_knowledge.md")

    instructions = ""
    with open(file_path, "r") as file:
        instructions = file.read()
    return instructions
