"""Reconciles a stored design with the tenant: for every step, adopt what exists, create what does not, and name what conflicts or cannot be done."""
from __future__ import annotations

import re
from typing import Any

from fastmcp import Context

from constants import constants
from mcpconfig.config import mcp
from tools.playbook import design_store, preflight
from utils import utils

ADOPT, CREATE, CONFLICT, BLOCKED = "ADOPT", "CREATE", "CONFLICT", "BLOCKED"


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _step(step: dict, action: str, reason: str = "", existing_id: str | None = None, **extra: Any) -> dict:
    out = {"id": step.get("id"), "type": step.get("type"), "level": step.get("level"), "name": step.get("name"), "action": action}
    if reason:
        out["reason"] = reason
    if existing_id:
        out["existingId"] = existing_id
    out.update(extra)
    return out


def resolve(doc: dict, tenant: dict) -> dict:
    """tenant: {applications: [{id, name, type, validated}], availableTypes: [names] | None, scopes: {name: id}, categories: [names] | None,
    assessments: {name: {id, controls: [{number, name, id}]}}, rules: {name: {where}}, workflows: {name: id}, chains: {blueprint folder: [workflow names] | None}}."""
    steps = [s for s in ((doc.get("spec") or {}).get("steps") or []) if isinstance(s, dict)]
    apps = {a["name"]: a for a in tenant.get("applications") or []}
    available = tenant.get("availableTypes")
    available_norm = {_norm(t) for t in available} if available is not None else None
    results: dict[str, dict] = {}
    risks: list[str] = []
    credentials: list[dict] = []

    for s in steps:
        c = s.get("config") if isinstance(s.get("config"), dict) else {}
        refs = s.get("refs") if isinstance(s.get("refs"), dict) else {}
        kind, name = s.get("type"), str(s.get("name") or "")
        if kind == "create_application":
            wanted = c.get("applicationType")
            existing = apps.get(name)
            if existing is not None:
                if _norm(existing.get("type")) == _norm(wanted):
                    results[s["id"]] = _step(s, ADOPT, "", existing.get("id"))
                    if not existing.get("validated") and _norm(wanted) != "nocredapp":
                        credentials.append({"application": name, "state": "exists, credentials not validated"})
                else:
                    results[s["id"]] = _step(s, CONFLICT, f"the tenant already has an application '{name}' of type {existing.get('type')}, the design needs {wanted}", existing.get("id"))
            elif available_norm is not None and _norm(wanted) not in available_norm:
                results[s["id"]] = _step(s, BLOCKED, f"the application type {wanted} is not installed in this tenant, so the application cannot be created")
            else:
                results[s["id"]] = _step(s, CREATE)
                if _norm(wanted) != "nocredapp":
                    credentials.append({"application": name, "state": "will be created: its credentials must be entered in the platform"})
        elif kind == "create_application_scope":
            existing = (tenant.get("scopes") or {}).get(name)
            results[s["id"]] = _step(s, ADOPT, "", existing) if existing else _step(s, CREATE)
        elif kind == "create_control":
            assessment = c.get("assessmentName")
            number = str(c.get("displayable") or c.get("alias") or "")
            held = (tenant.get("assessments") or {}).get(assessment)
            category = c.get("categoryName")
            if held is None:
                if category and tenant.get("categories") is not None and category not in tenant["categories"]:
                    results[s["id"]] = _step(s, BLOCKED, f"the category '{category}' does not exist in the tenant, and creating a category needs a decision")
                else:
                    results[s["id"]] = _step(s, CREATE, f"new assessment '{assessment}'" if number and "." not in number else "")
                continue
            by_number = {c2["number"]: c2 for c2 in held.get("controls") or []}
            there = by_number.get(number)
            same_name = [c2 for c2 in held.get("controls") or [] if c2["name"] == name]
            if len(same_name) == 1 and (there is None or there["name"] != name):
                found = same_name[0]
                results[s["id"]] = _step(s, ADOPT, f"exists in '{assessment}' as number {found['number']}; the design says {number}", found.get("id"))
            elif there is None:
                results[s["id"]] = _step(s, CREATE, f"in the existing assessment '{assessment}'")
            elif there["name"] == name:
                results[s["id"]] = _step(s, ADOPT, "", there.get("id"))
            else:
                free = (held.get("nextFreeNumber") or {}).get(number.rsplit(".", 1)[0] if "." in number else "")
                results[s["id"]] = _step(s, CONFLICT, f"number {number} in '{assessment}' is held by '{there['name']}'" + (f"; next free number: {free}" if free else ""), there.get("id"))
        elif kind == "create_rule":
            if c.get("sql"):
                results[s["id"]] = _step(s, CREATE, "SQL evidence")
                continue
            rule = (refs.get("rule") or name)
            found = (tenant.get("rules") or {}).get(rule) or {}
            where = found.get("where")
            if where in ("tenant", "catalog"):
                results[s["id"]] = _step(s, ADOPT, f"existing rule ({where})")
            elif where == "missing":
                results[s["id"]] = _step(s, CREATE, "a new rule", rule=rule, unproven=True)
                risks.append(f"'{rule}' is a new rule: it is unproven until it has been run")
            else:
                results[s["id"]] = _step(s, BLOCKED, f"the rule '{rule}' could not be looked up")
        elif kind in ("create_control_dependency", "link_control"):
            results[s["id"]] = _step(s, CREATE)
        elif kind == "create_workflow":
            folder = refs.get("workflow")
            chain = (tenant.get("chains") or {}).get(folder)
            existing = tenant.get("workflows") or {}
            if chain is None:
                results[s["id"]] = _step(s, CREATE, f"the workflows of the blueprint '{folder}' were not listed, so name collisions were not checked")
                risks.append(f"workflow collisions for the blueprint '{folder}' were not checked")
            else:
                taken = [n for n in chain if n in existing]
                if taken:
                    results[s["id"]] = _step(s, CONFLICT, f"{len(taken)} of the {len(chain)} workflows of '{folder}' already exist in the tenant: " + ", ".join(taken), taken=taken)
                else:
                    results[s["id"]] = _step(s, CREATE, f"{len(chain)} workflows")
        else:
            results[s["id"]] = _step(s, CREATE)

    for s in steps:
        if s.get("type") in ("create_control_dependency", "link_control"):
            c = s.get("config") if isinstance(s.get("config"), dict) else {}
            bad = [results[r]["name"] or r for r in (c.get("sourceControl"), c.get("targetControl")) if r in results and results[r]["action"] in (CONFLICT, BLOCKED)]
            if bad:
                results[s["id"]]["note"] = "depends on a step that is not resolved: " + ", ".join(bad)

    ordered = [results[s["id"]] for s in steps if s.get("id") in results]
    counts = {a: sum(1 for r in ordered if r["action"] == a) for a in (ADOPT, CREATE, CONFLICT, BLOCKED)}
    return {
        "ready": counts[CONFLICT] == 0 and counts[BLOCKED] == 0,
        "counts": counts,
        "conflicts": [r for r in ordered if r["action"] == CONFLICT],
        "blockers": [r for r in ordered if r["action"] == BLOCKED],
        "risks": risks,
        "credentialsNeeded": credentials,
        "steps": ordered,
    }


async def snapshot(doc: dict, ctx: Context | None) -> dict:
    """The tenant as `resolve` needs it, for the objects this design mentions."""
    raw = await preflight.gather_tenant(ctx)
    plans = raw["plans"] or []
    by_plan = {preflight._name(p): p for p in plans}

    async def get(path: str, query: dict) -> Any:
        return await utils.make_GET_API_call_to_CCow(path, ctx=ctx, query_params=query)

    steps = [s for s in ((doc.get("spec") or {}).get("steps") or []) if isinstance(s, dict)]
    assessments: dict[str, dict] = {}
    for name in sorted({(s.get("config") or {}).get("assessmentName") for s in steps if (s.get("config") or {}).get("assessmentName")}):
        plan = by_plan.get(name)
        if plan is None:
            continue
        rows = await preflight.fetch_all(get, constants.URL_PLAN_CONTROLS, {"plan_id": preflight._id(plan), "fields": "basic"}) or []
        tree = preflight.control_tree(rows)
        ids = {str(r.get("displayable") or r.get("alias") or ""): preflight._id(r) for r in rows}
        assessments[name] = {"id": preflight._id(plan), "controls": [{**c, "id": ids.get(c["number"])} for c in tree["controls"]], "nextFreeNumber": tree["nextFreeNumber"]}

    rules: dict[str, dict] = {}
    names = sorted({(s.get("refs") or {}).get("rule") or s.get("name") for s in steps if s.get("type") == "create_rule" and not (s.get("config") or {}).get("sql")})
    chains: dict[str, list[str] | None] = {}
    try:
        from tools.workflow import workflow
        if names:
            found = await workflow.find_rules_by_name(list(names), ctx)
            rules = {n: {"where": (r or {}).get("where")} for n, r in ((found or {}).get("rules") or {}).items()}
        for folder in sorted({(s.get("refs") or {}).get("workflow") for s in steps if s.get("type") == "create_workflow" and (s.get("refs") or {}).get("workflow")}):
            report = await workflow.inspect_workflow_blueprint(folder, brief=True, ctx=ctx)
            order = ((report or {}).get("chain") or {}).get("order")
            chains[folder] = list(order) if isinstance(order, list) else None
    except ImportError:
        pass

    apps = [{"id": preflight._id(a), "name": preflight._name(a), "type": preflight.app_type(a), "validated": bool(a.get("isValidated"))} for a in raw["apps"] or []]
    types = preflight.application_types_of(raw["app_configs"]) if raw["app_configs"] is not None else None
    return {
        "applications": apps,
        "availableTypes": [t["name"] for t in types] if types is not None else None,
        "scopes": {preflight._name(s): preflight._id(s) for s in raw["scopes"] or []},
        "categories": sorted(preflight._name(c) for c in raw["categories"]) if raw["categories"] is not None else None,
        "assessments": assessments,
        "rules": rules,
        "workflows": {preflight._name(w): preflight._id(w) for w in raw["configs"] or []},
        "chains": chains,
    }


@mcp.tool()
async def resolve_design(design_id: str, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Reconcile a design stored by check_use_case_design (by its designId) with the tenant, step by step, so that nothing is left for the build to discover. Read-only.
        Each step is ADOPT (it already exists as designed: its id is returned), CREATE, CONFLICT (something exists that clashes: a number held by another control, an application name with another
        type, workflow names already taken) or BLOCKED (it cannot be done: an application type not installed, a category that does not exist, a rule that could not be looked up).

    Returns:
        ready (no conflict and nothing blocked), counts, conflicts, blockers, risks (new rules are unproven until run), credentialsNeeded (applications that exist unvalidated or will be created, whose
        credentials a person must enter in the platform) and steps (every step with its action, reason and existingId). A design may be approved for an unattended build only when ready is true.
    """
    domain = preflight.identity_of(ctx).get("domainName")
    stored = design_store.load(design_id, domain)
    if stored is None:
        return {"success": False, "error": f"No design '{design_id}' for this tenant. Use the designId of a valid check_use_case_design call."}
    import yaml
    doc = yaml.safe_load(stored[0])
    tenant = await snapshot(doc, ctx)
    return {"success": True, "designId": design_id, **resolve(doc, tenant)}
