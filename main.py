import os
import signal
import sys
import traceback

from utils.debug import logger
from utils.auth import CCowOAuthProvider

# from tools.mcpconfig import mcp
from mcpconfig.config import mcp
from tools.assessments.config import config
from tools.assessments.run import run
from tools.graphdb import graphdb
from tools.dashboard import dashboard
from tools.assets import assets
from tools.help import help
from tools.workflow import workflow
from resources.graphdb import graphdb
from constants.constants import host
from mcp.server.auth.settings import AuthSettings
from prompts.workflow import workflow
from prompts.rule import rule
from tools.rules import rules


def signal_handler(sig, frame):
    print("Shutting down...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


@mcp.prompt()
async def generate_chart_prompt() -> list[str]:
    logger.info("generate_chart_prompt: \n")
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


if __name__ == "__main__":
    port = os.environ.get('CCOW_MCP_SERVER_PORT', "")
    portInInt = 0

    try:
        portInInt = int(port)
        print(f"Starting the server with SSE on port {portInInt}")
    except ValueError:
        print("Starting the server with stdio.")
        # print(f"Environment variable 'CCOW_MCP_SERVER_PORT' is not a valid integer: {port}")

    # Initialize and run the server

    if portInInt < 1:
        try:
            mcp.run(transport='stdio')
        except KeyboardInterrupt:
            logger.error(traceback.format_exc())
            print("\nExiting due to Ctrl+C")
            exit(0)
    else:
        mcp.settings.host = "0.0.0.0"
        mcp.settings.port = portInInt
        mcp.settings.auth = AuthSettings(issuer_url=host)
        mcp._auth_server_provider = CCowOAuthProvider()
        mcp.run(transport='sse')
