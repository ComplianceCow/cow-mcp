import os

from mcpconfig.config import mcp


@mcp.prompt()
def rule_generation_prompt() -> str:

    script_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(script_dir, "rule.md")

    instructions = ""
    with open(file_path, "r") as file:
        instructions = file.read()
    return instructions
