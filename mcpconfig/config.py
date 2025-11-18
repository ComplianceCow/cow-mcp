# from mcp.server.fastmcp import FastMCP
import fastmcp
import os
from constants import constants
from functools import wraps
from typing import Optional, Callable, Any, Dict
from fastmcp import Context
from utils.debug import logger


if not constants.ENABLE_CCOW_API_TOOLS:

    port = os.environ.get('CCOW_MCP_SERVER_PORT', "")
    portInInt = 0

    try:
        portInInt = int(port)
        print(f"Starting the server with streamable on port {portInInt}")
    except ValueError:
        print("Starting the server with stdio.")
        # print(f"Environment variable 'CCOW_MCP_SERVER_PORT' is not a valid integer: {port}")

    # Initialize and run the server

    if portInInt > 1:
        fastmcp.settings.host = "0.0.0.0"
        fastmcp.settings.port = portInInt

mcp = fastmcp.FastMCP("ComplianceCow")

def get_header_value(headers: Dict[str, Any], key: str, default: str = "") -> str:
    try:
        if not isinstance(headers, dict):
            return default
        if not isinstance(key, str):
            return default

        return headers.get(key) or headers.get(key.lower()) or default
    except Exception:
        return default


def require_auth(func: Callable):
    """Decorator to require authentication for a tool"""
    @wraps(func)
    async def wrapper(*args, ctx=None, **kwargs):
        # Extract token
        auth_token = None
        if ctx and hasattr(ctx, 'request_context'):
            req_ctx = ctx.request_context
            if req_ctx and hasattr(req_ctx, 'meta') and req_ctx.meta:
                websocket_headers = req_ctx.meta.get('websocket_headers', {})
                auth_token = websocket_headers.get('authtoken')

        if not auth_token:
            return "Error: Authentication required"

        # Add token to kwargs for the function to use
        kwargs['auth_token'] = auth_token
        return await func(*args, **kwargs)

    return wrapper

def get_cc_headers(ctx: Optional[Context]) -> Optional[dict[str, str]]:
    """Extract auth token from request context"""

    cc_headers = {"X-CALLER": "mcp_server-user_intent"}

    logger.debug(f"[get_cc_headers] ctx: {ctx}")

    if ctx and hasattr(ctx, 'request_context'):
        logger.debug(f"[get_cc_headers] ctx.request_context: {ctx.request_context}")
        if ctx.request_context:
            # if hasattr(ctx.request_context, '__dict__'):
            #     websocket_headers = ctx.request_context.__dict__.get('websocket_headers', {})
            #     print(f"Websocket headers: {websocket_headers}")
            #     if isinstance(websocket_headers, dict):
            #         cc_headers = websocket_headers.copy()
            #         print(f"cc_headers inside: {cc_headers}")
            #     else:
            #         print("websocket_headers is not a dict")
            
            if hasattr(ctx.request_context, 'meta') and  hasattr(ctx.request_context.meta, 'websocket_headers'):
                logger.debug(f"[get_cc_headers] websocket_headers: {ctx.request_context.meta.websocket_headers}")
                if isinstance(ctx.request_context.meta.websocket_headers, dict):
                    cc_headers = ctx.request_context.meta.websocket_headers.copy()
                else:
                    print("meta.websocket_headers is not a dict")

            print(f"cc_headers inside: {cc_headers}")
            logger.debug(f"[get_cc_headers] cc_headers (final): {cc_headers}")

    if not bool(cc_headers):
        headers = dict(ctx.get_http_request().headers)
        if not cc_headers.get(constants.AUTH_HEADER_KEY):
            authoriation = get_header_value(headers,constants.AUTH_HEADER_KEY)
            if authoriation:
                cc_headers[constants.AUTH_HEADER_KEY]=authoriation
            else:
                cc_headers=constants.headers

        elif not cc_headers.get(constants.X_COW_SECURITY_CONTEXT):
            cc_headers[constants.X_COW_SECURITY_CONTEXT] = get_header_value(constants.X_COW_SECURITY_CONTEXT)

    logger.debug(f"[get_cc_headers] cc_headers (returning): {cc_headers}")

    return cc_headers