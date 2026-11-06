"""The READMEs of the rules a blueprint's workflows run. A rule's README can say which columns its input evidence must have (for example the columns a ticket
workflow needs in the evidence it updates), so what a use case's evidence must contain is read from them."""
from __future__ import annotations

from tools.workflow import blueprint_inspect


def rule_names(specs: dict[str, dict]) -> list[str]:
    return sorted({r["name"] for spec in specs.values() for r in blueprint_inspect.needs(spec)["rules"]})


def collect(specs: dict[str, dict], found: dict[str, str | None]) -> dict:
    """`found`: per rule name, its README text, "" when the rule has none, or None when it could not be looked up."""
    used: dict[str, list[str]] = {}
    for workflow, spec in specs.items():
        for rule in blueprint_inspect.needs(spec)["rules"]:
            used.setdefault(rule["name"], []).append(workflow)
    return {
        "ruleReadmes": {name: {"usedBy": sorted(workflows), "readme": found[name]} for name, workflows in sorted(used.items()) if found.get(name)},
        "rulesWithoutReadme": sorted(name for name in used if found.get(name) == ""),
        "ruleReadmesUnchecked": sorted(name for name in used if found.get(name) is None),
    }
