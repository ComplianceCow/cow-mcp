
from mcpconfig.config import mcp
import os

# use_neo4j_graph_data = bool(os.getenv("USE_NEO4J_GRAPH_DATA", "true").lower().strip())

@mcp.prompt()
def insights_generation_prompt() -> str:

    script_dir = os.path.dirname(os.path.abspath(__file__))
    # if use_neo4j_graph_data:
    #     file_path = os.path.join(script_dir, "insights_knowledge_with_graph.md")
    # else:
    file_path = os.path.join(script_dir, "insights_knowledge.md")

    instructions = ""
    with open(file_path, "r") as file:
        instructions = file.read()
    return instructions
