"""The columns the evidence feeding a control really has, as the platform holds them. A check's author names columns from the design and the READMEs;
this reads them from the control itself (the evidence of the controls it takes its data from, with the schema the platform stores), so the page can offer
columns that are known to exist. It reads the platform's source summary of a control; nothing is changed."""
from __future__ import annotations

from typing import Any

from fastmcp import Context

from mcpconfig.config import mcp
from constants import constants
from utils import utils

MAX_EVIDENCES, MAX_COLUMNS = 12, 80


def kind_of(*types: Any) -> str:
    """text, number, time or flag, from the platform's name for the column's type."""
    t = " ".join(str(x or "") for x in types).upper()
    if "BOOL" in t:
        return "flag"
    if any(w in t for w in ("TIMESTAMP", "DATETIME", "DATE", "TIME")):
        return "time"
    if any(w in t for w in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMBER", "NUMERIC", "LONG")):
        return "number"
    return "text"


def _linked(lineage: Any):
    for entry in lineage or []:
        for control in (entry or {}).get("linkedFrom") or []:
            yield control
            yield from _linked(control.get("lineage"))


def evidences_of(summary: dict) -> list[dict]:
    """[{name, id, control, columns: [{name, kind, type}]}] for the evidence of every control this one takes data from, each evidence once."""
    out: list[dict] = []
    seen: set[tuple] = set()
    for control in _linked(summary.get("lineage")):
        for ev in control.get("evidences") or []:
            name = ev.get("name")
            if not name or str(name).lower() in ("logfile", "auditfile"):
                continue
            key = ev.get("id") or (control.get("controlId") or control.get("controlName"), name)
            columns = [{"name": c["name"], "kind": kind_of(c.get("type"), c.get("fieldDataType")), "type": c.get("type") or c.get("fieldDataType") or ""}
                       for c in ev.get("columnsInfo") or [] if c.get("name")]
            if key in seen or not columns:
                continue
            seen.add(key)
            out.append({"name": name, "id": ev.get("id") or "", "control": control.get("controlName") or "", "columns": columns[:MAX_COLUMNS]})
    return out[:MAX_EVIDENCES]


async def _summary(control_id: str, ctx: Context | None) -> dict:
    """The platform's source summary of a control, or {"success": False, "error": ...}."""
    if not control_id or not str(control_id).strip():
        return {"success": False, "error": "control_id is mandatory"}
    resp = await utils.make_API_call_to_CCow_and_get_response(constants.URL_PLAN_CONTROLS_FETCH_SOURCE_SUMMARY, "POST", {"controlID": str(control_id).strip()}, ctx=ctx)
    if isinstance(resp, str):
        return {"success": False, "error": resp}
    if not isinstance(resp, dict) or "Message" in resp:
        return {"success": False, "error": str(resp)}
    return {"success": True, "data": resp}


async def _evidence_schema(evidence_id: str, ctx: Context | None) -> list[dict] | None:
    """The columns the platform stores for one evidence that exists (a run produced it), or None when it cannot be read."""
    output = await utils.make_API_call_to_CCow({
        "evidenceID": evidence_id, "templateType": "evidence", "status": ["active"], "returnFormat": "json",
        "isSrcFetchCall": True, "isUserPriority": True, "considerFileSizeRestriction": True, "viewEvidenceFlow": True,
    }, constants.URL_DATAHANDLER_FETCH_DATA, ctx=ctx)
    if not isinstance(output, dict) or "error" in output or output.get("Message") == "CANNOT_FIND_THE_FILE":
        return None
    return columns_of_schema(((output.get("config") or {}).get("srcConfig")) or [])


def columns_of_schema(items: list) -> list[dict]:
    return [{"name": i["name"], "kind": kind_of(i.get("type")), "type": i.get("type") or ""} for i in items if isinstance(i, dict) and i.get("name") and i.get("type")][:MAX_COLUMNS]


async def read(control_id: str, ctx: Context | None, fetch=None, evidence_id: str = "", evidence_name: str = "", fetch_schema=None) -> dict:
    fetch = fetch or _summary
    answer = await fetch(control_id, ctx)
    body = answer.model_dump() if hasattr(answer, "model_dump") else answer
    if not isinstance(body, dict) or not body.get("success") or not body.get("data"):
        return {"success": False, "error": (body or {}).get("error") if isinstance(body, dict) else "the platform did not answer", "control_id": control_id}
    data = body["data"]
    control = data.get("controlName") or ""
    evidences = evidences_of(data)
    if evidence_id.strip():
        columns = await (fetch_schema or _evidence_schema)(evidence_id.strip(), ctx)
        if columns and not any(e["id"] == evidence_id.strip() for e in evidences):
            evidences.insert(0, {"name": evidence_name.strip() or evidence_id.strip(), "id": evidence_id.strip(), "control": control, "columns": columns})
        elif columns is None:
            return {"success": False, "error": "the schema of that evidence could not be read: it may not exist yet (no run has produced it)", "control_id": control_id}
    result: dict = {"success": True, "control_id": control_id, "control": control, "assessment": data.get("assessmentName") or "", "evidences": evidences[:MAX_EVIDENCES]}
    if not evidences:
        result["note"] = "no evidence with a known schema is known for this control yet: a schema exists once a run has produced the evidence (pass its evidence_id), or when other controls are linked to feed this one"
    return result


@mcp.tool()
async def evidence_columns(control_id: str, evidence_id: str = "", evidence_name: str = "", ctx: Context | None = None) -> dict:
    """
    Purpose:
        Say which columns the evidence feeding a control really has, with the type the platform stores for each, so a person can be offered columns that exist. It reads
        the control's source summary (the evidence of the controls it takes its data from); nothing is changed. Call it for a check's control once the control exists
        in the tenant (its id is in the specialists' answers): the page shows the columns it returns as checked against the evidence, next to the ones you listed in
        compliance_logic.

    Inputs:
        control_id: the id of the control (the plan control id a specialist returned), copied exactly.
        evidence_id: optional. The id of an evidence of that control that a run has produced (from the run details), to read its columns. Without it, only evidence
            of controls linked to feed this control is known, which is often none: the platform stores no column list for a rule's output until a run has made the evidence.
        evidence_name: optional. The evidence's name, to label it.

    Returns:
        success, control, assessment and evidences: each {name, id, control (where it comes from), columns: [{name, kind: text|number|time|flag, type}]}.
        With success false, error says why. An empty evidences list with a note means no schema is known yet.
    """
    return await read(control_id, ctx, evidence_id=evidence_id, evidence_name=evidence_name)
