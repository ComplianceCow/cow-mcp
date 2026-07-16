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

def get_header_value(headers: Any, key: str, default: str = "") -> str:
    """Case-insensitive header lookup.

    Works with both a plain ``dict`` and Starlette's ``Headers`` object
    (returned by ``request.headers``), which is *not* a ``dict`` subclass.
    """
    try:
        if headers is None or not isinstance(key, str):
            return default
        # Both dict and Starlette Headers expose ``.get``; Headers.get is
        # already case-insensitive, dict is not — so try the lowercase key too.
        if not hasattr(headers, "get"):
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

def _get_request_headers(req_ctx: Any) -> Any:
    """Return the HTTP request headers from the request context, or None.

    Accessing ``request`` can raise when there is no active HTTP request
    (e.g. stdio transport), so this is defensive.
    """
    try:
        request = getattr(req_ctx, "request", None)
        return getattr(request, "headers", None) if request is not None else None
    except Exception:
        return None


def _get_meta_websocket_headers(req_ctx: Any) -> Optional[dict[str, Any]]:
    """Return the legacy ``_meta.websocket_headers`` dict, or None.

    ``meta`` may be a dict-like or an object exposing ``websocket_headers``.
    """
    meta = getattr(req_ctx, "meta", None)
    if meta is None:
        return None
    if isinstance(meta, dict):
        websocket_headers = meta.get("websocket_headers")
    else:
        websocket_headers = getattr(meta, "websocket_headers", None)
    return websocket_headers if isinstance(websocket_headers, dict) else None


def get_cc_headers(ctx: Optional[Context]) -> Optional[dict[str, str]]:
    """Extract ComplianceCow headers from the request context.

    Priority (highest first):
    1. HTTP request headers — moocp's DynamicHeaderClient forwards the
       allow-listed session headers here per-request. This is now the primary
       path.
    2. JSON-RPC ``_meta.websocket_headers`` in the request body — legacy
       fallback for older clients that inline headers in the payload.
    3. Static ``constants.headers`` as a last resort.
    """
    cc_headers: dict[str, str] = {}

    if ctx and getattr(ctx, "request_context", None):
        req_ctx = ctx.request_context

        # 1. Preferred: HTTP headers forwarded per-request.
        http_headers = _get_request_headers(req_ctx)
        if http_headers is not None:
            for key in (constants.AUTH_HEADER_KEY, constants.X_COW_SECURITY_CONTEXT):
                value = get_header_value(http_headers, key)
                if value:
                    cc_headers[key] = value

        # 2. Legacy fallback: only if the HTTP path didn't yield auth.
        if not cc_headers.get(constants.AUTH_HEADER_KEY):
            websocket_headers = _get_meta_websocket_headers(req_ctx)
            if websocket_headers:
                # Meta values win for keys they carry; keep any HTTP-only extras.
                cc_headers = {**cc_headers, **websocket_headers}

    # 3. Last resort: static constants.
    if not (cc_headers.get(constants.AUTH_HEADER_KEY) or cc_headers.get(constants.AUTH_HEADER_KEY.lower())):
        if isinstance(constants.headers, dict):
            for key, value in constants.headers.items():
                cc_headers.setdefault(key, value)

    cc_headers.setdefault("X-CALLER", "mcp_server-user_intent")

    # Log header names only — values contain auth tokens / secrets.
    logger.debug(f"[get_cc_headers] returning header keys: {list(cc_headers.keys())}")

    return cc_headers