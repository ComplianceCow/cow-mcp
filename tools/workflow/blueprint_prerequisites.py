"""Compares what a blueprint workflow needs with what the tenant has, so a missing piece is found before anyone is asked about it."""
from __future__ import annotations

from typing import Any

from tools.workflow import blueprint_inspect


def _walk(node: Any, key: str):
    """Every dict under `node` that has the key."""
    if isinstance(node, dict):
        if key in node:
            yield node
        for value in node.values():
            yield from _walk(value, key)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value, key)


def tenant_events(listing: Any) -> list[dict]:
    return [{"displayable": e["displayable"], "id": e.get("id"), "type": e.get("type")} for e in _walk(listing, "displayable")]


def tenant_functions(listing: Any) -> list[dict]:
    return [{"name": f.get("name"), "displayable": f.get("displayable"), "id": f.get("id")} for f in _walk(listing, "displayable")]


def check(spec: dict, events: list[dict] | None, functions: list[dict] | None, rule_places: dict[str, str]) -> dict:
    """`rule_places` says, per rule name, where it was found: "tenant", "catalog" (the platform publishes it when the workflow is created), "missing", or
    "unchecked" when the lookup failed. A listing that could not be read (None) leaves its things unchecked rather than missing."""
    wanted = blueprint_inspect.needs(spec)
    have_events = {e["displayable"]: e for e in events or []}
    have_functions = {name for f in functions or [] for name in (f["name"], f["displayable"]) if name}
    report = {
        "events": [
            {**e, "found": None if events is None else e["displayable"] in have_events, "tenantId": (have_events.get(e["displayable"]) or {}).get("id")}
            for e in wanted["events"]
        ],
        "rules": [{**r, "where": rule_places.get(r["name"], "unchecked")} for r in wanted["rules"]],
        "functions": [{**f, "found": None if functions is None else (f["name"] in have_functions or f["displayable"] in have_functions)} for f in wanted["functions"]],
    }
    missing, unchecked = [], []
    for e in report["events"]:
        if e["found"] is None:
            unchecked.append(f"the event '{e['displayable']}'")
        elif not e["found"]:
            custom = e["type"] == "CUSTOM_EVENT"
            missing.append(f"the {'custom ' if custom else ''}event '{e['displayable']}' does not exist in the tenant" + (" (create it with create_workflow_custom_event)" if custom else ""))
    for r in report["rules"]:
        if r["where"] == "missing":
            missing.append(f"the rule '{r['name']}' is in neither the tenant nor the catalog")
        elif r["where"] == "unchecked":
            unchecked.append(f"the rule '{r['name']}'")
    for f in report["functions"]:
        if f["found"] is None:
            unchecked.append(f"the function '{f['name']}'")
        elif not f["found"]:
            missing.append(f"the function '{f['name']}' does not exist in the tenant")
    report["publishedOnCreate"] = [r["name"] for r in report["rules"] if r["where"] == "catalog"]
    report["missing"] = missing
    report["unchecked"] = unchecked
    return report


def summarize(report: dict) -> dict:
    """The prerequisite report without its per-item lists: how many of each were found, and what is missing, unchecked or published on creation."""
    events, rules, functions = report["events"], report["rules"], report["functions"]
    return {
        "events": f"{sum(1 for e in events if e['found'])} of {len(events)} found",
        "rules": f"{len(rules)}: " + ", ".join(f"{sum(1 for r in rules if r['where'] == place)} {place}" for place in ("tenant", "catalog", "missing", "unchecked") if any(r["where"] == place for r in rules)) if rules else "0",
        "functions": f"{sum(1 for f in functions if f['found'])} of {len(functions)} found",
        "publishedOnCreate": report["publishedOnCreate"],
        "missing": report["missing"],
        "unchecked": report["unchecked"],
    }
