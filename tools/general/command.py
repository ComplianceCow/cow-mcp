from mcpconfig.config import mcp
from utils.debug import logger
from utils import utils
from constants import constants
from fastmcp import Context

if constants.ENABLE_SHELL_EXECUTION:
    @mcp.tool()
    async def execute_shell_command(cmd: str, ctx: Context | None = None) -> dict:
        """
        Execute exactly one shell command or one shell pipeline in an isolated sandbox.

        Follow these rules:
        - Keep the full task self-contained in single call.
        - Each call is isolated. Files, temporary data, and other resources created in one call
        will not exist in the next call.
        - Do not rely on a later call to continue reading a file created by an earlier call.
        - Output returned by this tool is limited by the sandbox service configuration.
        - If the raw output may exceed that limit, use a single command or single pipeline that
        extracts, filters, paginates, or summarizes only the data needed for the task.
        - If filtering is needed, perform that filtering within the same single command or pipeline.

        Returns combined stdout and stderr from the sandbox service.
        """
        try:
            logger.info("execute_shell_command: \n")

            if not cmd or not cmd.strip():
                logger.error("execute_shell_command error: Command is empty\n")
                return {"success": False, "error": "Command cannot be empty."}

            resp = await utils.make_API_call_to_CCow_and_get_response(
                constants.SANDBOX_EXECUTE_URL,
                "POST",
                {"cmd": cmd},
                ctx=ctx
            )

            if isinstance(resp, dict):
                if resp.get("Message"):
                    logger.error("execute_shell_command error: {}\n".format(resp))
                    return {"success": False, "error": resp}

                output = resp.get("output", "")
                logger.debug("execute_shell_command output: {}\n".format(output))
                return {"success": True, "output": output}

            logger.error("execute_shell_command error: Unexpected response type {}\n".format(type(resp)))
            return {"success": False, "error": "Command execution failed."}

        except Exception as e:
            logger.error("execute_shell_command error: {}\n".format(e))
            return {"success": False, "error": f"Error executing command: {e}"}
