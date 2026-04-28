import os

from mcpconfig.config import mcp


@mcp.prompt()
def assessment_knowledge() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    general_path = os.path.join(script_dir, "assessment_creation_knowledge.md")
    general = ""

    with open(general_path, "r") as file:
        general = file.read()

    return general
