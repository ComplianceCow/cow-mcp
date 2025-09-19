
from mcpconfig.config import mcp


@mcp.prompt()
async def generate_chart_prompt() -> list[str]:
    return [
        {
            "role": "user",
            "content": f"Generate a chart with "
            f"Compliance Overview section containing Total controls; Controls Status: each status"
            f"Progress bar chart for 'controlAssignmentStatus'"
            f"Fetch dashboard data for latest quarterly"
            # f"show 'Completed' status in orange color"
            f"for these user data."
        }
    ]
