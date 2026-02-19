import os

from mcpconfig.config import mcp


@mcp.prompt()
def metric_knowledge() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    general_path = os.path.join(script_dir, "metric_general_knowledge.md")

    general = ""

    with open(general_path, "r") as file:
        general = file.read()

    return general
