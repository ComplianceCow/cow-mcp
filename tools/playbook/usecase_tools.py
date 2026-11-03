"""The tools that check and push a use-case YAML into the Playbook graph. The rules are in usecase_push.py.

Pushing writes to a catalog every tenant shares, so neither tool is registered unless PLAYBOOK_PUSH_ENABLED is set, and only a recipe written
for a person who approves each push should list push_use_case among its tools. validate_use_case_yaml writes nothing.
"""
from __future__ import annotations

import os
from typing import Any

import httpx
from fastmcp import Context

from constants import constants
from mcpconfig.config import mcp
from tools.playbook import usecase_push as push_logic
from utils import utils

TIMEOUT = float(os.environ.get("PLAYBOOK_PUSH_TIMEOUT", "120") or 120)


def enabled() -> bool:
    return os.environ.get("PLAYBOOK_PUSH_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _poster(ctx: Context | None, route: str, transport: httpx.AsyncBaseTransport | None = None) -> push_logic.Post:
    """Sends the request with the caller's own credentials and keeps the status and the whole body: the shared helper keeps only a
    description of an error, and a validation answer is a list."""
    async def post(payload: dict) -> tuple[int | None, Any, str | None]:
        try:
            async with httpx.AsyncClient(transport=transport) as client:
                response = await client.post(utils.host + route, json=payload, headers=utils.get_cc_headers(ctx), timeout=TIMEOUT)
        except httpx.TimeoutException:
            return None, None, f"the backend did not answer within {int(TIMEOUT)} seconds, so it is not known what it concluded"
        except httpx.HTTPError as e:
            return None, None, f"the backend could not be reached ({type(e).__name__}), so nothing was sent through"
        try:
            return response.status_code, response.json(), None
        except ValueError:
            return response.status_code, response.text, None
    return post


@mcp.tool()
async def validate_use_case_yaml(yaml_text: str, source_name: str | None = None, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Ask the backend whether a use-case YAML is valid. It writes nothing, and can be called as often as you like while you write the YAML.

    Inputs:
        yaml_text: the whole use case, as YAML text.
        source_name: the file name it would be recorded under, such as "servicenow.yaml". Left out, it is the use case's id plus .yaml.

    Returns:
        {valid: true} when the backend accepts it. {valid: false, validation_errors, error_count, problem} when it does not: fix every listed
        error and call again. {valid: null, problem} when the backend could not be asked or answered in a form not known: that is not a yes.
    """
    prepared = push_logic.prepare(yaml_text, source_name)
    checked = await push_logic.validate(prepared, _poster(ctx, constants.URL_PLAYBOOK_VALIDATE))
    return {**push_logic.summary(prepared), **checked}


@mcp.tool()
async def push_use_case(
    yaml_text: str,
    source_name: str | None = None,
    replace: bool = False,
    approval: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """
    Purpose:
        Push a use-case YAML into the Playbook catalog. The catalog is shared by every tenant, so this is done only with a person's approval
        of exactly what is pushed.

    How to call it, always in two steps:
        1. Call it with the YAML and NO approval. Nothing is written. The backend checks the document and you get a preview: the id, version,
           name, lifecycle, how many steps of each type, and, only if the document is valid, an `approval` code. Show the preview to the person
           and ask whether to push it. A document that is not valid gets its errors and no approval code: fix them and start again.
        2. Only if they say yes, call it again with the same yaml_text, source_name and replace, and the `approval` from the preview. A YAML
           that changed after the preview needs a new preview and a new yes.

    Inputs:
        yaml_text: the whole use case, as YAML text.
        source_name: the file name to record it under, such as "servicenow.yaml". Left out, it is the use case's id plus .yaml.
        replace: true only when the person has agreed to overwrite a version that is already in the catalog.
        approval: the code from the preview. Without it nothing is written.

    Returns:
        Step 1: {pushed: false, valid, needs_approval, preview fields, approval?, validation_errors?}.
        Step 2: {pushed, problem?, validation_errors?, conflict?, loaded?, backend}. `pushed` is true only when the backend says it wrote the
        document. A conflict means this id and version are already in the catalog: do not retry with replace unless the person agrees to
        overwrite it.
    """
    prepared = push_logic.prepare(yaml_text, source_name, replace)
    if approval is None:
        return await push_logic.review(prepared, _poster(ctx, constants.URL_PLAYBOOK_VALIDATE))
    return await push_logic.push(prepared, approval, _poster(ctx, constants.URL_PLAYBOOK_LOAD))
