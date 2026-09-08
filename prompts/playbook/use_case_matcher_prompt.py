import os

from mcpconfig.config import mcp


@mcp.prompt()
def use_case_matcher_knowledge() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))

    prompt_path = os.path.join(
        script_dir,
        "use_case_matcher.md",
    )

    with open(prompt_path, "r") as file:
        return file.read()