"""Runs an assessment (or reads a run that exists) and says, for every control, whether its evidence was produced and, when not, why."""
from __future__ import annotations

import asyncio
import re
import time
from typing import Any, Awaitable, Callable

from fastmcp import Context

from constants import constants
from mcpconfig.config import mcp
from utils import utils

TERMINAL = {"completed", "failed", "error", "cancelled", "canceled", "aborted", "completedwitherrors"}
FAILED_EVIDENCE = {"failed", "error", "errored", "aborted", "cancelled", "canceled"}
NOT_STARTED_EVIDENCE = {"yet to start", "not started", "pending", "queued", "new"}

# What a LogFile error says about the cause: (pattern, kind, what to do)
LOG_PATTERNS = [
    (r"inputfile.* missing|missing in user inputs|input .* is (missing|required)", "RULE_INPUT_MISSING",
     "a task of the rule has an input that nothing supplies: the rule's internal wiring (its ioMap) or a required input of the control is incomplete"),
    (r"unauthori[sz]ed|\b401\b|\b403\b|forbidden|invalid (api )?(key|token|credential)|authentication", "CREDENTIALS",
     "the application refused the credentials: check that the application is validated and its credentials are current"),
    (r"invalid url|no such host|connection (refused|reset)|timeout|dial tcp|name resolution", "CONNECTION",
     "the rule could not reach its source or its input: an upstream output may be missing, or the application's URL is wrong"),
    (r"syntax error|no such (table|column)|ambiguous column|parser error|sql", "SQL_ERROR",
     "the SQL of the rule does not run against its inputs: a column or table name does not match the evidence it reads"),
]


def classify_log_error(text: str) -> tuple[str, str]:
    lowered = text.lower()
    for pattern, kind, hint in LOG_PATTERNS:
        if re.search(pattern, lowered):
            return kind, hint
    return "RULE_ERROR", "the rule reported an error; read its message"


def classify_control(control_no: str, evidences: list[dict], log_error: str | None, dependencies: list[dict], verdicts: dict[str, str]) -> dict:
    """One verdict for a control.

    evidences: [{name, status, rows}] for the evidence other than LogFile; rows is the number of sample rows read, or None when they could not be read.
    dependencies: [{input, source, crossAssessment}] where source is the number of the control that supplies the input.
    verdicts: the verdicts already decided for the controls this one depends on."""
    crossing = [d for d in dependencies if d.get("crossAssessment")]
    if crossing:
        names = ", ".join(f"{d['input']} from control {d['source']}" for d in crossing)
        starts = all(str(e.get("status", "")).lower() in NOT_STARTED_EVIDENCE for e in evidences)
        if starts:
            return {"verdict": "CROSS_ASSESSMENT_DEPENDENCY", "cause": f"takes {names}, which belongs to another assessment: a run executes one assessment, so this control never starts",
                    "fix": "combine data from two assessments with link_control into a higher-layer control and a SQL rule over the linked evidence"}
    failed_upstream = [d["source"] for d in dependencies if verdicts.get(d["source"], "OK") not in ("OK", "UNREADABLE")]
    if log_error:
        kind, hint = classify_log_error(log_error)
        if failed_upstream and kind in ("CONNECTION", "RULE_INPUT_MISSING"):
            return {"verdict": "UPSTREAM_FAILED", "cause": f"error '{log_error}' while its input from control {', '.join(failed_upstream)} is missing", "fix": f"fix control {', '.join(failed_upstream)} first"}
        return {"verdict": kind, "cause": log_error, "fix": hint}
    statuses = [str(e.get("status", "")).lower() for e in evidences]
    if any(s in FAILED_EVIDENCE for s in statuses):
        return {"verdict": "RULE_ERROR", "cause": "the evidence is marked failed and the rule left no error message", "fix": "open the control run in the platform for its log"}
    if evidences and all(s in NOT_STARTED_EVIDENCE for s in statuses):
        if failed_upstream:
            return {"verdict": "UPSTREAM_FAILED", "cause": f"never started: its input from control {', '.join(failed_upstream)} was not produced", "fix": f"fix control {', '.join(failed_upstream)} first"}
        return {"verdict": "NOT_STARTED", "cause": "the control never started and nothing upstream failed", "fix": "check its dependencies and that its application is validated"}
    readable = [e for e in evidences if e.get("rows") is not None]
    if not readable:
        return {"verdict": "UNREADABLE", "cause": "the evidence completed but its data could not be read here", "fix": "open it in the platform"}
    if all(e["rows"] == 0 for e in readable):
        return {"verdict": "EMPTY", "cause": "the evidence completed with no rows", "fix": "check the rule's filter and that the source holds matching data"}
    return {"verdict": "OK", "cause": "", "fix": ""}


def order_by_dependency(controls: dict[str, list[dict]]) -> list[str]:
    """Control numbers so that a control comes after those it depends on."""
    done: list[str] = []
    pending = dict(controls)
    while pending:
        ready = [n for n, deps in pending.items() if all(d["source"] in done or d["source"] not in controls for d in deps)]
        if not ready:
            ready = list(pending)[:1]
        for n in sorted(ready):
            done.append(n)
            pending.pop(n)
    return done


def summarize(controls: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for c in controls:
        counts[c["verdict"]] = counts.get(c["verdict"], 0) + 1
    return {"counts": counts, "ok": bool(controls) and all(c["verdict"] in ("OK", "UNREADABLE") for c in controls)}


async def wait_for_run(status_of: Callable[[], Awaitable[str | None]], seconds: int, step: float = 10.0) -> str | None:
    deadline = time.monotonic() + seconds
    status = await status_of()
    while (status is None or status.lower() not in TERMINAL) and time.monotonic() < deadline:
        await asyncio.sleep(step)
        status = await status_of()
    return status


def _json(value: Any) -> Any:
    return value if isinstance(value, (dict, list)) else None


async def _dependencies(plan_id: str, get: Callable[[str, dict], Awaitable[Any]]) -> dict[str, list[dict]]:
    """{control number: [{input, source, crossAssessment}]} for the controls of a plan."""
    rows = await get(constants.URL_PLAN_CONTROLS, {"plan_id": plan_id, "fields": "basic", "page": 1, "page_size": 200})
    items = rows.get("items") if isinstance(rows, dict) else None
    if not isinstance(items, list):
        return {}
    by_id = {r.get("id"): str(r.get("displayable") or r.get("alias") or "") for r in items}
    out: dict[str, list[dict]] = {}
    for r in items:
        number = str(r.get("displayable") or r.get("alias") or "")
        deps = []
        for name, source in (r.get("dependedInputs") or {}).items():
            src_id = source.get("planControlId") if isinstance(source, dict) else None
            deps.append({"input": name, "source": by_id.get(src_id, str(src_id)[:8]), "crossAssessment": src_id not in by_id})
        out[number] = deps
    return out


async def verify(assessment_id: str, run_id: str | None, name: str, wait_seconds: int, ctx: Context | None, adapters: dict | None = None, samples: int = 0) -> dict:
    """The tool's logic. `adapters` replaces the platform calls in tests."""
    from tools.rules import action_rules

    async def get(path: str, query: dict) -> Any:
        return await utils.make_GET_API_call_to_CCow(path, ctx=ctx, query_params=query)

    a = {
        "run": lambda: action_rules.run_assessment(assessment_id, name, "Verification run started by verify_assessment. Automated actions are disabled.", ctx),
        "runs": lambda: action_rules.get_all_recent_assessment_runs(assessment_id, ctx),
        "details": lambda rid: action_rules.get_assessment_run_details(rid, assessment_id, ctx),
        "evidence_rows": lambda control_run_id: get(constants.URL_PLAN_INSTANCE_EVIDENCES, {"plan_instance_control_id": control_run_id}),
        "evidence_data": lambda evidence_id: action_rules.get_run_evidence_data(evidence_id, ctx),
        "dependencies": lambda: _dependencies(assessment_id, get),
        **(adapters or {}),
    }
    started = False
    if not run_id:
        result = _json(await a["run"]())
        run_id = ((result or {}).get("data") or {}).get("runId") if result and result.get("success") else None
        if not run_id:
            return {"success": False, "error": f"The run could not be started: {result}"}
        started = True

    async def status_of() -> str | None:
        runs = _json(await a["runs"]())
        for row in (runs or {}).get("data") or []:
            if row.get("assessmentRunId") == run_id:
                return row.get("status")
        return None

    status = await wait_for_run(status_of, wait_seconds, step=0 if adapters else 10.0)
    if status is None or status.lower() not in TERMINAL:
        return {"success": True, "runId": run_id, "started": started, "status": status, "finished": False, "error": f"The run had not finished after {wait_seconds} seconds; call again with run_id."}

    details = _json(await a["details"](run_id)) or {}
    run_controls = ((details.get("data") or {}).get("controls")) or []
    deps_by_number = _json(await a["dependencies"]()) or {}
    raw: dict[str, dict] = {}
    for c in run_controls:
        number = str(c.get("controlNo"))
        statuses = _json(await a["evidence_rows"](c["id"])) or {}
        status_by_name: dict[str, str] = {}
        for item in statuses.get("items") or []:
            status_by_name[item.get("name")] = item.get("status")
        evidences, log_error = [], None
        for e in c.get("evidence") or []:
            data = _json(await a["evidence_data"](e["id"]))
            items = (((data or {}).get("data") or {}).get("items")) if data and data.get("success") else None
            if e.get("name") == "LogFile":
                if items and isinstance(items[0], dict) and items[0].get("Error"):
                    log_error = str(items[0]["Error"])
                continue
            entry = {"name": e.get("name"), "status": status_by_name.get(e.get("name"), "Completed" if items is not None else "Yet to start"), "rows": None if items is None else len(items)}
            if samples and items:
                entry["sample"] = items[:samples]
            evidences.append(entry)
        raw[number] = {"control": c, "evidences": evidences, "log_error": log_error}
    verdicts: dict[str, str] = {}
    results: dict[str, dict] = {}
    for number in order_by_dependency({n: deps_by_number.get(n, []) for n in raw}):
        r = raw[number]
        v = classify_control(number, r["evidences"], r["log_error"], deps_by_number.get(number, []), verdicts)
        verdicts[number] = v["verdict"]
        results[number] = {"controlNo": number, "name": r["control"].get("name"), **v, "evidence": r["evidences"]}
    ordered = [results[n] for n in sorted(results, key=lambda n: [int(p) if p.isdigit() else 0 for p in n.split(".")])]
    return {"success": True, "runId": run_id, "started": started, "status": status, "finished": True, "controls": ordered, **summarize(ordered)}


@mcp.tool()
async def verify_assessment(assessment_id: str, run_id: str | None = None, name: str = "Verification run", wait_seconds: int = 540, samples: int = 0, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Say, for every control of an assessment run, whether its evidence was produced and, when it was not, why. With no run_id it STARTS a real run of the assessment (automated actions such as
        tickets are disabled), waits for it to finish and judges it; with a run_id it only judges that run and changes nothing.

    Inputs:
        assessment_id: the assessment (plan) id.
        run_id: an existing run to judge; leave out to start a new one.
        name: the name of the run when one is started.
        wait_seconds: how long to wait for the run to finish (default 540, which stays inside the 660 seconds a caller is given).
        samples: how many rows (at most 3) of each evidence to return in `sample`, to show a person what was produced; 0 returns none.

    Returns:
        success, runId, started, status, finished, controls (per control: controlNo, name, verdict, cause, fix, evidence: [{name, status, rows}]), counts per verdict and ok (true when every
        control produced evidence). Verdicts: OK; EMPTY (completed, no rows); NOT_STARTED; UPSTREAM_FAILED (an input it needs was not produced); CROSS_ASSESSMENT_DEPENDENCY (takes an input from
        another assessment, so it never starts); RULE_INPUT_MISSING, CREDENTIALS, CONNECTION, SQL_ERROR, RULE_ERROR (the rule's own error, classified); UNREADABLE.
    """
    return await verify(assessment_id, run_id, name, max(0, min(int(wait_seconds), 1800)), ctx, samples=max(0, min(int(samples), 3)))
