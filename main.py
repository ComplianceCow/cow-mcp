import os
import signal
import sys
import traceback

# from mcp.server.auth.settings import AuthSettings

from constants.constants import host
from mcpconfig.config import mcp
from tools.general import general
from utils.auth import CCowOAuthProvider
from utils.debug import logger

mcp_tools_to_be_included = os.getenv("MCP_TOOLS_TO_BE_INCLUDED", "rules,insights,workflow").lower().strip()

MCP_TOOLS = [t.strip() for t in mcp_tools_to_be_included.split(",") if t.strip()]

if "insights" in MCP_TOOLS:
    from prompts.insights import insights
    from resources.graphdb import graphdb
    from tools.assessments.config import config
    from tools.assessments.run import run
    from tools.assets import assets
    from tools.dashboard import dashboard
    from tools.graphdb import graphdb
    from tools.help import help

if "rules" in MCP_TOOLS:
    from prompts.rule import rule
    from tools.rules import rules

if "workflow" in MCP_TOOLS:
    from prompts.workflow import workflow
    from tools.workflow import workflow

if "assistant" in MCP_TOOLS:
    from tools.assistant import assistant
    from prompts.assistant import assistant

def signal_handler(sig, frame):
    print("Shutting down...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)



if __name__ == "__main__":
    port = os.environ.get('CCOW_MCP_SERVER_PORT', "")
    portInInt = 0

    try:
        portInInt = int(port)
        print(f"Starting the server with streamable on port {portInInt}")
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
        # mcp.settings.auth = AuthSettings(issuer_url=host)
        # mcp._auth_server_provider = CCowOAuthProvider()
        mcp.run(transport='streamable-http')
