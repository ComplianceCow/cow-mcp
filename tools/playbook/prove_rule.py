"""Runs a rule once and judges it by what every task wrote to its log: a task is marked completed even when it logged an error, so status alone proves nothing."""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
import time
from typing import Any, Callable

from fastmcp import Context

from constants import constants
from mcpconfig.config import mcp
from tools.playbook import verify_run
from utils import utils, wsutils

NO_APPLICATION = {"nocredapp", "nocred", ""}


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def input_payload(structure: dict) -> list[dict]:
    """The rule's inputs as execute-rule wants them: every field of the definition, the value taken from its default and copied into defaultValue."""
    meta = ((structure.get("spec") or {}).get("inputsMeta__")) or []
    return [{**m, "value": m.get("defaultValue"), "defaultValue": m.get("defaultValue")} for m in meta if isinstance(m, dict)]


def application_needs(structure: dict) -> dict[str, dict]:
    """{application type tag: the appTags of the first task that needs it}, leaving out the tasks that need no application."""
    needs: dict[str, dict] = {}
    for task in ((structure.get("spec") or {}).get("tasks")) or []:
        tags = task.get("appTags") if isinstance(task, dict) else None
        types = (tags or {}).get("appType") or []
        tag = str(types[0]) if types else ""
        if _norm(tag) not in NO_APPLICATION and tag not in needs:
            needs[tag] = tags
    return needs


def _wanted(chosen: Any) -> list[str]:
    """The applications the caller named, as a list of ids or names (a mapping contributes its values)."""
    if isinstance(chosen, dict):
        chosen = list(chosen.values())
    return [str(c).strip() for c in (chosen or []) if str(c).strip()]


def pick_applications(needs: dict[str, dict], tenant_apps: list[dict], chosen: Any = None) -> tuple[list[dict], list[str], dict[str, list[str]]]:
    """The applications to run with, the application types for which the tenant has no validated application, and the types for which it has several
    and the caller has not said which: a guess between two applications would prove the rule against the wrong system."""
    wanted = _wanted(chosen)
    picked, missing, ambiguous = [], [], {}
    for tag, tags in needs.items():
        candidates = [a for a in tenant_apps if _norm(str(a.get("appType", "")).split("::")[0]) == _norm(tag) and a.get("isValidated")]
        named = [a for a in candidates if a.get("id") in wanted or a.get("credentialName") in wanted]
        if named:
            candidates = named[:1]
        if not candidates:
            missing.append(tag)
        elif len(candidates) > 1:
            ambiguous[tag] = [str(a.get("credentialName")) for a in candidates]
        else:
            app = candidates[0]
            picked.append({"applicationType": str(app.get("appType", "")).split("::")[0], "applicationId": app.get("id"), "appTags": tags, "name": app.get("credentialName")})
    return picked, missing, ambiguous


def log_records(display_content: Any) -> list[dict]:
    """The records of a task's log, from the text the file reader returns."""
    if isinstance(display_content, list):
        return [r for r in display_content if isinstance(r, dict)]
    if isinstance(display_content, str):
        try:
            value = json.loads(display_content)
        except ValueError:
            return []
        return [r for r in value if isinstance(r, dict)] if isinstance(value, list) else []
    return []


def judge(status: str | None, tasks: list[dict]) -> dict:
    """tasks: in execution order, each {name, status, errors: [messages], outputs: [{name, rows}]}. The first error is the cause: what fails after it is a consequence of it."""
    failing = [t for t in tasks if t.get("errors") or str(t.get("status", "")).upper() == "ERROR"]
    if status and status.upper() == "ERROR" and not failing:
        return {"verdict": "FAIL", "firstError": {"task": None, "message": "the execution ended in ERROR without a task error", "kind": "RULE_ERROR", "fix": "open the execution in the platform"}, "consequences": []}
    if not failing:
        empty = [o["name"] for t in tasks for o in t.get("outputs", []) if o.get("rows") == 0 or o.get("sizeKb") == 0]
        hollow = [o["name"] for t in tasks for o in t.get("outputs", []) if (o.get("emptyShare") or 0) > 0.5]
        warnings = (["ran without errors but produced no rows: " + ", ".join(empty)] if empty else []) + (["the rows are mostly empty (the source may have returned nothing and the rule made a placeholder row): " + ", ".join(hollow)] if hollow else [])
        return {"verdict": "PASS", "firstError": None, "consequences": [], **({"warning": "; ".join(warnings)} if warnings else {})}
    first = failing[0]
    message = (first.get("errors") or [first.get("error") or "the task failed"])[0]
    kind, fix = verify_run.classify_log_error(str(message))
    consequences = [{"task": t["name"], "message": (t.get("errors") or [""])[0]} for t in failing[1:]]
    return {"verdict": "FAIL", "firstError": {"task": first["name"], "message": message, "kind": kind, "fix": fix}, "consequences": consequences}


async def prove(rule_name: str, chosen: Any, wait_seconds: int, ctx: Context | None, adapters: dict | None = None, samples: int = 3) -> dict:
    """The tool's logic. `adapters` replaces the platform calls in tests."""
    from tools.rules import rules as rules_module

    def sync(fn: Callable, *args: Any) -> Any:
        return asyncio.to_thread(fn, *args)

    async def tenant_apps() -> list[dict]:
        result = await utils.make_GET_API_call_to_CCow(constants.URL_CREATE_APPLICATION, ctx=ctx, query_params={"page": 1, "page_size": 200})
        return (result or {}).get("items", []) if isinstance(result, dict) else []

    def read_structure() -> dict | None:
        response = wsutils.get(path=wsutils.build_api_url(endpoint=constants.URL_FETCH_RULES), params={"name": rule_name}, header=wsutils.create_header(ctx))
        for item in (response.get("items") if isinstance(response, dict) else None) or []:
            if isinstance(item, dict) and (item.get("meta") or {}).get("name") == rule_name:
                return item
        return None

    async def execute(payload: dict) -> Any:
        return await sync(lambda: wsutils.post(path=wsutils.build_api_url(endpoint=constants.URL_EXECUTE_RULE), data=json.dumps(payload), header=wsutils.create_header(ctx)))

    a = {
        "structure": lambda: sync(read_structure),
        "apps": tenant_apps,
        "execute": execute,
        "progress": lambda execution_id: sync(rules_module.fetch_execution_progress, rule_name, execution_id, ctx),
        "file": lambda url: sync(rules_module.fetch_output_file, url, ctx),
        **(adapters or {}),
    }
    structure = await a["structure"]()
    if not isinstance(structure, dict) or not (structure.get("spec") or {}):
        return {"success": False, "rule": rule_name, "verdict": "NOT_FOUND", "error": f"The rule '{rule_name}' could not be read from the tenant."}

    needs = application_needs(structure)
    applications, missing, ambiguous = pick_applications(needs, await a["apps"](), chosen)
    if ambiguous:
        return {"success": True, "rule": rule_name, "verdict": "NEEDS_CHOICE", "candidates": ambiguous,
                "fix": "several validated applications fit: call again with `applications` naming the one the rule is for (its name or id), for example the application the design names for it"}
    if missing:
        return {"success": True, "rule": rule_name, "verdict": "NEEDS_APPLICATION", "missingApplicationTypes": missing,
                "fix": "the tenant has no validated application of " + ", ".join(missing) + ": create it and enter its credentials in the platform, then prove the rule"}

    today = dt.date.today().isoformat()
    started = await a["execute"]({"fromDate": today, "toDate": today, "ruleName": rule_name, "ruleInputs": input_payload(structure), "applications": applications})
    execution_id = (started or {}).get("id") if isinstance(started, dict) else None
    if not execution_id:
        return {"success": False, "rule": rule_name, "verdict": "FAIL", "error": f"The execution could not be started: {started}"}

    deadline = time.monotonic() + wait_seconds
    progress: dict = {}
    while True:
        progress = await a["progress"](execution_id)
        if isinstance(progress, dict) and progress.get("continue_polling") is False:
            break
        if time.monotonic() >= deadline:
            return {"success": True, "rule": rule_name, "verdict": "TIMEOUT", "executionId": execution_id, "error": f"The execution had not finished after {wait_seconds} seconds."}
        await asyncio.sleep(0 if adapters else 3)

    tasks: list[dict] = []
    for line in progress.get("display_lines") or []:
        if not isinstance(line, dict) or not line.get("task_name"):
            continue
        errors, outputs = [], []
        for name, url in (line.get("outputs") or {}).items():
            read = await a["file"](url)
            read = read if isinstance(read, dict) else {}
            fmt = str(read.get("file_format") or "").lower()
            records = log_records(read.get("display_content")) if fmt in ("json", "") else []
            if name == "LogFile":
                errors += [str(r["Error"]) for r in records if r.get("Error")]
            else:
                rows = len(records) if fmt == "json" else None
                outputs.append({"name": name, "format": fmt or None, "sizeKb": read.get("file_size_kb"), "rows": rows, **({"sample": records[:samples], "emptyShare": verify_run.empty_share(records[:samples])} if samples and records else {})})
        if line.get("error"):
            errors.append(str(line["error"]))
        tasks.append({"name": line["task_name"], "status": line.get("status"), "errors": errors, "outputs": outputs})
    return {"success": True, "rule": rule_name, "executionId": execution_id, "status": progress.get("status"), "applications": [x["name"] for x in applications], "tasks": tasks, **judge(progress.get("status"), tasks)}


@mcp.tool()
async def prove_rule(rule_name: str, applications: list[str] | dict[str, str] | None = None, wait_seconds: int = 120, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Run a rule once and say whether it works. A rule can be created without error and still fail when run, and the engine marks a task completed even when it wrote an error to its log, so this reads
        the log of every task in order: the FIRST error is the cause, and what fails after it is only a consequence. It runs the rule for real against the tenant's validated applications (reads data;
        the rule is not attached to anything and nothing is changed). Use it on every rule you build before relying on it.

    Inputs:
        rule_name: the rule, as published in the tenant.
        applications: the applications to run with, as a list of names or ids (the application the rule is for). Needed only when the tenant has several validated applications of a type the rule
            needs (a generic HTTP rule fits every HttpRequest application): the tool never guesses between them. With one validated application of a type, it is used.
        wait_seconds: how long to wait for the execution (default 120).

    Returns:
        verdict: PASS, FAIL, NEEDS_APPLICATION (no validated application of a type the rule needs), NEEDS_CHOICE (several do: candidates lists them), NOT_FOUND or TIMEOUT. With a run: tasks (name, status, errors, outputs with row counts and a sample),
        firstError (task, message, kind, fix), consequences (the later errors) and, for a PASS with an empty output, a warning.
    """
    return await prove(rule_name, applications, max(10, min(int(wait_seconds), 600)), ctx)
