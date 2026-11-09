"""One read-only call that says what the tenant already holds, so a design or a creation never guesses it."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from fastmcp import Context

from constants import constants
from mcpconfig.config import get_cc_headers, mcp
from utils import utils

PAGE_SIZE = 200
MAX_PAGES = 10


def _name(item: dict) -> str:
    return str(item.get("name") or item.get("credentialName") or (item.get("metadata") or {}).get("name") or "")


def _id(item: dict) -> str:
    return str(item.get("id") or (item.get("status") or {}).get("id") or "")


def app_type(item: dict) -> str:
    """The application type as the platform names it, without the trailing '::' (HttpRequest, OktaConnector, ...)."""
    return str(item.get("appType") or "").split("::")[0]


def _credential(entry: Any) -> str | None:
    """`<name> <version>` from a credential type given as [name, version] or {name, version}."""
    if isinstance(entry, (list, tuple)) and entry:
        return " ".join(str(x) for x in entry[:2]).strip()
    if isinstance(entry, dict) and entry.get("name"):
        return f"{entry.get('name')} {entry.get('version') or ''}".strip()
    return None


def application_types_of(app_configs: list[dict]) -> list[dict]:
    """The application types this tenant can create applications of, each with its credential types written `<name> <version>`. A type that appears
    more than once is listed once, with the credential types of all its entries."""
    merged: dict[str, dict] = {}
    for item in app_configs:
        meta, spec = item.get("meta") or {}, item.get("spec") or {}
        name = meta.get("name")
        if not name:
            continue
        raw = ((item.get("status") or {}).get("internal") or {}).get("credentialTypes") or (item.get("status") or {}).get("credentialTypes") or spec.get("credentialTypes") or []
        entry = merged.setdefault(name, {"name": name, "displayName": meta.get("displayName"), "credentialTypes": []})
        for credential in filter(None, map(_credential, raw)):
            if credential not in entry["credentialTypes"]:
                entry["credentialTypes"].append(credential)
    return list(merged.values())


def summarize(identity: dict, apps: list[dict] | None, scopes: list[dict] | None, plans: list[dict] | None,
              categories: list[dict] | None, configs: list[dict] | None, bindings: list[dict] | None, app_configs: list[dict] | None = None) -> dict:
    """Each list is the rows the platform returned, or None when that lookup failed."""
    failed = [label for label, rows in (("applications", apps), ("applicationScopes", scopes), ("assessments", plans), ("categories", categories),
                                        ("workflows", configs), ("workflowBindings", bindings), ("availableApplicationTypes", app_configs)) if rows is None]
    apps, scopes, plans, categories, configs, bindings, app_configs = (rows or [] for rows in (apps, scopes, plans, categories, configs, bindings, app_configs))
    bound = {_name(b) for b in bindings}

    applications = [{"name": _name(a), "type": app_type(a), "credentialType": a.get("credentialType"), "validated": bool(a.get("isValidated"))} for a in apps]
    assessments = [{"name": _name(p), "id": _id(p), "level": "L1 asset" if p.get("type") == "integration" else "L2/L3 assessment", "category": p.get("categoryName")} for p in plans]
    workflows = [{"name": _name(c), "id": _id(c), "hasBinding": _name(c) in bound} for c in configs]
    scope_rows = [{"name": _name(s), "id": _id(s), "status": s.get("status")} for s in scopes]

    by_type: dict[str, list[str]] = {}
    for a in applications:
        by_type.setdefault(a["type"], []).append(a["name"])

    notes: list[str] = []
    if "availableApplicationTypes" not in failed:
        notes.append("availableApplicationTypes are the only types this tenant can create applications of, with their credential types. A type a design needs that is not listed is not installed here: say so, and give its credential type as unverified.")
    if applications:
        notes.append("Applications exist. A design step may reuse one only when both its name and its type match; the same name with another type, or the right type under another name, is a conflict to settle before creating (see applicationsByType).")
    unvalidated = [a["name"] for a in applications if not a["validated"] and a["type"] != "NoCredApp"]
    if unvalidated:
        notes.append("Applications without validated credentials (an assessment that uses them cannot fetch data until they are set): " + ", ".join(unvalidated))
    if workflows:
        notes.append("Workflows exist: creating a workflow from a blueprint whose names are already taken conflicts with them. They are not yours to delete or change unless the user says so.")
    if assessments:
        notes.append("Assessments exist: an L2/L3 assessment with the designed name is reused as it is, with its own category, root control and numbering.")

    domain = identity.get("domainName")
    return {
        "success": True,
        "tenant": {"domain": domain, "user": identity.get("username")},
        "isEmpty": not (applications or scope_rows or assessments or workflows),
        "counts": {"applications": len(applications), "applicationScopes": len(scope_rows), "assessments": len(assessments), "workflows": len(workflows)},
        "applications": applications,
        "applicationsByType": by_type,
        "availableApplicationTypes": application_types_of(app_configs),
        "applicationScopes": scope_rows,
        "assessments": assessments,
        "categories": sorted(_name(c) for c in categories if _name(c)),
        "workflows": workflows,
        "notes": notes,
        "lookupFailed": failed,
    }


def rows_of(response: Any) -> list[dict] | None:
    """The rows of a list response, or None when the call failed (an error string or an error object)."""
    if isinstance(response, list):
        return [r for r in response if isinstance(r, dict)]
    if isinstance(response, dict) and isinstance(response.get("items"), list) and "error" not in response:
        return [r for r in response["items"] if isinstance(r, dict)]
    if isinstance(response, dict) and "items" not in response and "error" not in response and not response:
        return []
    return None


async def fetch_all(get: Callable[[str, dict], Awaitable[Any]], path: str, query: dict | None = None) -> list[dict] | None:
    """Every page of a list endpoint (None when any page fails: a partial inventory would mislead)."""
    out: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        response = await get(path, {**(query or {}), "page": page, "page_size": PAGE_SIZE})
        rows = rows_of(response)
        if rows is None:
            return None
        out += rows
        total_pages = response.get("TotalPage") if isinstance(response, dict) else None
        if not isinstance(total_pages, int) or page >= total_pages:
            return out
    return out


def identity_of(ctx: Context | None) -> dict:
    raw = (get_cc_headers(ctx) or {}).get(constants.X_COW_SECURITY_CONTEXT)
    try:
        value = json.loads(raw) if raw else {}
    except ValueError:
        value = {}
    return value if isinstance(value, dict) else {}


async def gather_tenant(ctx: Context | None) -> dict:
    """The raw rows of everything the tenant holds, each None when its lookup failed."""
    async def get(path: str, query: dict) -> Any:
        return await utils.make_GET_API_call_to_CCow(path, ctx=ctx, query_params=query)

    return {
        "identity": identity_of(ctx),
        "apps": await fetch_all(get, constants.URL_CREATE_APPLICATION),
        "scopes": await fetch_all(get, constants.URL_CREATE_APPLICATION_SCOPE),
        "plans": await fetch_all(get, constants.URL_PLANS, {"fields": "basic"}),
        "categories": rows_of(await get(constants.URL_ASSESSMENT_CATEGORIES, {})),
        "configs": await fetch_all(get, constants.URL_WORKFLOW_CREATE, {"fields": "meta"}),
        "bindings": await fetch_all(get, constants.URL_WORKFLOW_BINDINGS),
        "app_configs": await fetch_all(get, constants.URL_APPLICATION_CONFIGS, {"isStatusToBeIncluded": "true"}),
    }


@mcp.tool()
async def preflight_tenant(ctx: Context | None = None) -> dict:
    """
    Purpose:
        Say what the tenant already holds before anything is designed or created: applications (name, type, credentials validated), the application types the tenant can create applications of (availableApplicationTypes, with credential types), application scopes, assessments (L1 assets and L2/L3
        assessments, with their category), categories and workflows. Read-only. Call it once at the start of a design or a creation and use its answer instead of assuming the tenant is empty,
        or that an application, scope, assessment or workflow does or does not exist.

    Returns:
        tenant, isEmpty, counts, applications, applicationsByType, availableApplicationTypes, applicationScopes, assessments, categories, workflows, notes (what to do about what exists) and lookupFailed (lists that could
        not be read: treat those as unknown, never as empty).
    """
    t = await gather_tenant(ctx)
    return summarize(t["identity"], t["apps"], t["scopes"], t["plans"], t["categories"], t["configs"], t["bindings"], t["app_configs"])



def _number_key(number: str) -> list[int]:
    return [int(part) if part.isdigit() else 0 for part in str(number).split(".")]


def control_tree(rows: list[dict]) -> dict:
    """The controls of one assessment as {controls: [{number, name}] in number order, nextFreeNumber: {parent number ("" for the top level): the next free number under it}}."""
    controls = [{"number": str(r.get("displayable") or r.get("alias") or ""), "name": str(r.get("name") or "")} for r in rows]
    controls = [c for c in controls if c["number"]]
    controls.sort(key=lambda c: _number_key(c["number"]))
    taken = {c["number"] for c in controls}
    parents = {""} | {c["number"].rsplit(".", 1)[0] for c in controls if "." in c["number"]} | {c["number"] for c in controls}
    free: dict[str, str] = {}
    for parent in sorted(parents, key=_number_key):
        prefix = f"{parent}." if parent else ""
        used = [int(c["number"][len(prefix):].split(".")[0]) for c in controls if c["number"].startswith(prefix) and c["number"][len(prefix):].split(".")[0].isdigit() and c["number"] != parent]
        n = (max(used) + 1) if used else 1
        while f"{prefix}{n}" in taken:
            n += 1
        free[parent] = f"{prefix}{n}"
    return {"controls": controls, "nextFreeNumber": free}


@mcp.tool()
async def describe_assessments(names: list[str], ctx: Context | None = None) -> dict:
    """
    Purpose:
        The controls (number and name, parents included) of existing assessments, with the next free number under each parent. Use it for every existing assessment a design reuses, so that no new control
        takes a number that is already held by a control with another name. Read-only. Give up to 20 names, exactly as preflight_tenant lists them.

    Returns:
        assessments: {name: {id, level, controls: [{number, name}], nextFreeNumber: {parent number ("" is the top level): next free number}}}; notFound: names with no assessment; lookupFailed: names whose
        controls could not be read (unknown, not empty).
    """
    async def get(path: str, query: dict) -> Any:
        return await utils.make_GET_API_call_to_CCow(path, ctx=ctx, query_params=query)

    plans = await fetch_all(get, constants.URL_PLANS, {"fields": "basic"})
    if plans is None:
        return {"success": False, "error": "Could not read the assessments of the tenant."}
    wanted = list(dict.fromkeys(n.strip() for n in names if isinstance(n, str) and n.strip()))[:20]
    by_name = {_name(p): p for p in plans}
    out: dict[str, dict] = {}
    not_found, failed = [], []
    for name in wanted:
        plan = by_name.get(name)
        if plan is None:
            not_found.append(name)
            continue
        rows = await fetch_all(get, constants.URL_PLAN_CONTROLS, {"plan_id": _id(plan), "fields": "basic"})
        if rows is None:
            failed.append(name)
            continue
        out[name] = {"id": _id(plan), "level": "L1 asset" if plan.get("type") == "integration" else "L2/L3 assessment", **control_tree(rows)}
    return {"success": True, "assessments": out, "notFound": not_found, "lookupFailed": failed}
