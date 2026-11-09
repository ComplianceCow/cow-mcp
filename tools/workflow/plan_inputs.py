"""Reads the inputs an assessment (plan) holds, so what was added to it can be checked instead of taken from a tool's success message."""
from __future__ import annotations

from typing import Any


def failed(response: Any) -> bool:
    """True for a message string or an error body, including the Message and Description body the platform returns for a plan that does not exist."""
    if isinstance(response, str):
        return True
    if not isinstance(response, dict):
        return True
    return any(key in response for key in ("error", "ErrorMessage", "ErrorDetails")) or ("Message" in response and "Description" in response)


def describe(plan_id: str, plan: Any) -> dict:
    """{success, plan_id, name, inputs: [{key, type, required, description, fileName, value, hasValue}]}; a file input has its file name and no value."""
    if failed(plan) or str(plan.get("id") or "") != plan_id:
        return {"success": False, "plan_id": plan_id, "error": f"no assessment with the id {plan_id}: {plan}"}
    found = []
    for key, item in sorted((plan.get("inputs") or {}).items()):
        item = item if isinstance(item, dict) else {}
        default = item.get("defaultvalue")
        is_file = isinstance(default, dict)
        found.append({
            "key": key,
            "type": item.get("type"),
            "required": bool(item.get("isrequired")),
            "description": item.get("description") or "",
            "fileName": default.get("FileName") if is_file else None,
            "value": None if is_file else default,
            "hasValue": bool(default.get("FileName") or default.get("FileHash")) if is_file else default not in (None, ""),
        })
    return {"success": True, "plan_id": plan_id, "name": plan.get("name"), "inputs": found}
