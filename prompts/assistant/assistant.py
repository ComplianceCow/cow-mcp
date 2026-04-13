import os

from mcpconfig.config import mcp


@mcp.prompt()
def assistant_knowledge() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    general_path = os.path.join(script_dir, "assistant_general_knowledge.md")
    domain_path = os.path.join(script_dir, "domain_specific.md")

    general = ""
    domain = ""

    with open(general_path, "r") as file:
        general = file.read()

    # OPTIONAL: Only attach if domain file exists
    if os.path.exists(domain_path):
        with open(domain_path, "r") as file:
            domain = file.read()

    return general + "\n\n" + domain
