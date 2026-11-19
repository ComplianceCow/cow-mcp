"""Ask the user something and keep waiting for the answer even when they have left the chat. The ask is registered with the assistant service, which
remembers where the chat stood and tells the platform's workflows about it; a workflow the tenant has bound to that event asks the user on Slack or Teams
if they have not replied after a few minutes."""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from fastmcp import Context

from mcpconfig.config import mcp
from utils import utils

ASKS_URL = "/v1/assistant-gen-ai/asks"
SESSION_KEY = "agent-session-id"
EXPIRES_IN_HOURS = 24

Call = Callable[[str, str, dict], Awaitable[tuple[int, dict]]]


def session_id_of(ctx: Context | None) -> str:
    """The id of the session this call belongs to, which the agent host puts in the request metadata. Empty when it is not there."""
    meta = getattr(getattr(ctx, "request_context", None), "meta", None)
    value = meta.get(SESSION_KEY) if isinstance(meta, dict) else getattr(meta, SESSION_KEY, None)
    return value if isinstance(value, str) else ""


def _calling(ctx: Context | None) -> Call:
    async def call(method: str, path: str, body: dict) -> tuple[int, dict]:
        response = await utils.make_API_call_to_CCow_and_get_response(path, method, body, return_raw=True, ctx=ctx)
        if not hasattr(response, "status_code"):
            return 0, {"message": response if isinstance(response, str) else "the service did not answer"}
        try:
            answer = response.json() if response.content else {}
        except ValueError:
            answer = {}
        return response.status_code, answer if isinstance(answer, dict) else {}
    return call


def _waiting(ask_id: str, escalation: str, kind: str, wait_minutes: int) -> dict:
    if escalation == "unavailable":
        message = "Waiting for the user to reply in this chat. End your turn now and do not repeat the question."
    elif kind == "credentials":
        message = (f"Waiting for the user. If they do not reply in {wait_minutes} minutes they are sent a link to this chat, never asked for the credentials elsewhere. "
                   "End your turn now and do not repeat the request.")
    else:
        message = (f"Waiting for the user. If they do not reply in {wait_minutes} minutes they are asked on Slack or Teams and their answer arrives in this chat. "
                   "End your turn now and do not repeat the question.")
    return {"success": True, "status": "waiting", "ask_id": ask_id, "escalation": escalation, "message": message}


async def request(question: str, kind: str = "question", options: list[str] | None = None, wait_minutes: int = 5, *,
                  call: Call, session_id: str) -> dict:
    if not session_id:
        return {"success": False, "error": "This can only be used from a chat with the user."}
    body: dict[str, Any] = {"agent_session_id": session_id, "kind": kind, "question": question,
                            "wait_minutes": wait_minutes, "expires_in_hours": EXPIRES_IN_HOURS}
    if options:
        body["options"] = options
    status, answer = await call("POST", ASKS_URL, body)
    if status not in (200, 201):
        return {"success": False, "error": answer.get("message") or "The ask could not be registered."}
    ask_id = answer.get("ask_id", "")
    if status == 200:
        return _waiting(ask_id, "already_scheduled", kind, wait_minutes)
    return _waiting(ask_id, "scheduled" if answer.get("escalation") == "started" else "unavailable", kind, wait_minutes)


@mcp.tool()
async def request_user_input(question: str, kind: str = "question", options: list[str] | None = None, wait_minutes: int = 5, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Ask the user something you need before you can go on, and make sure they are reached even if they have left this chat. Call it as the LAST thing you do in a
        turn, right after you write the question in your reply, and then end your turn. If the user has not replied after wait_minutes they are asked on Slack or Teams,
        and their answer arrives in this chat as their next message. Do not use it for a question you can answer yourself, and never repeat the question afterwards.

    Inputs:
        question: what you are asking, in plain words, up to 1500 characters. Never put a password, key or token in it.
        kind: question (a free-text answer), approval (the user picks one of options) or credentials (the user must enter secrets in the web app: they are only sent a link,
            never asked for the secret elsewhere).
        options: required for approval: up to 5 short choices of at most 40 characters. The answer is exactly one of them.
        wait_minutes: how long to wait before asking elsewhere, 1 to 60. Default 5.

    Returns:
        success, and with it status "waiting", the ask_id and a message saying what to do next (end your turn). With success false, error says why; then just ask in this chat as usual.
    """
    return await request(question, kind, options, wait_minutes, call=_calling(ctx), session_id=session_id_of(ctx))
