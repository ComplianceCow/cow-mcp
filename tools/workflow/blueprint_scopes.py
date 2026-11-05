"""Compares the application types the rules of a workflow need with the applications of the application scope the workflow runs them under.

When a workflow runs a rule activity, the platform finds the scope by the activity's `appScopeName`, builds an application group from the applications in
it and runs the rule's tasks against that group. A workflow is created without that being checked, and a scope that is missing or has no application for a
task's type fails when the workflow runs."""
from __future__ import annotations

from typing import Any

from tools.workflow import blueprint_inspect

NO_CREDENTIAL = "nocredapp"


def normalize(name: Any) -> str:
    """`JiraCloud::` (an application's type) and `jiracloud` (the tag on a rule or task) are the same type."""
    return str(name or "").split("::")[0].strip().lower()


def _tags(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    return [normalize(v) for v in values if normalize(v)]


def rule_app_types(rule: dict) -> set[str]:
    """Every application type a catalog rule names: its own label and the tag of each of its tasks."""
    found = set(_tags(((rule.get("meta") or {}).get("labels") or {}).get("appType")))
    for task in (rule.get("spec") or {}).get("tasks") or []:
        found.update(_tags(((task or {}).get("appTags") or {}).get("appType")))
    return found


def check(spec: dict, rule_types: dict[str, set[str] | None], scopes: dict[str, dict | None]) -> dict:
    """`rule_types`: per rule name, the types it needs, or None when they could not be read.
    `scopes`: per scope name, {"types": the types of its applications} when it exists, {"types": None} when it does not, or None when the lookup failed."""
    needs: dict[str | None, dict[str, list[str]]] = {}
    missing, unchecked = [], []
    for rule in blueprint_inspect.needs(spec)["rules"]:
        types = rule_types.get(rule["name"])
        if types is None:
            unchecked.append(f"the application types of the rule '{rule['name']}'")
            continue
        for kind in types:
            needs.setdefault(rule.get("appScope") or None, {}).setdefault(kind, []).append(rule["name"])

    report = []
    for scope, wanted in sorted(needs.items(), key=lambda item: str(item[0])):
        if scope is None:
            lacking = {k: v for k, v in wanted.items() if k != NO_CREDENTIAL}
            if lacking:
                missing.append("rules without an application scope need applications: " + _describe(lacking))
            continue
        found = scopes.get(scope)
        entry = {"scope": scope, "needs": sorted(wanted)}
        if found is None:
            unchecked.append(f"the application scope '{scope}'")
            report.append({**entry, "exists": None})
            continue
        have = found.get("types")
        if have is None:
            missing.append(f"the application scope '{scope}' does not exist; create it with applications of these types: {_describe(wanted)}")
            report.append({**entry, "exists": False, "missing": sorted(wanted)})
            continue
        lacking = {k: v for k, v in wanted.items() if k not in have}
        if lacking:
            missing.append(f"the application scope '{scope}' has no application of the type {_describe(lacking)}")
        report.append({**entry, "exists": True, "has": sorted(have), "missing": sorted(lacking)})
    return {"scopes": report, "missing": missing, "unchecked": unchecked}


def _describe(by_type: dict[str, list[str]]) -> str:
    return "; ".join(f"{kind} (for {', '.join(sorted(set(rules)))})" for kind, rules in sorted(by_type.items()))
