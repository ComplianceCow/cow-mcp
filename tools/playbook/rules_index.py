"""A compact index of the catalog rules the designer can pick from: one line per rule, name and purpose only."""
from __future__ import annotations

from typing import Any

from fastmcp import Context

from mcpconfig.config import mcp
from tools.workflow import rule_lookup
from utils import rule

PURPOSE_LIMIT = 160
LOCAL_MARK = "[local rule, not from the platform: find_rule_by_name says if it is unvetted]"


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def index_lines(rules: list[Any]) -> list[str]:
    """`Name: purpose` per rule (the description when the purpose is missing or only repeats the name), each purpose cut to PURPOSE_LIMIT characters, sorted by name, one per name."""
    seen: dict[str, str] = {}
    for item in rules:
        get = item.get if isinstance(item, dict) else lambda key, default=None: getattr(item, key, default)
        name = _text(get("name"))
        if not name or name in seen:
            continue
        purpose = _text(get("purpose"))
        if not purpose or purpose.lower() == name.lower():
            description = _text(get("description"))
            purpose = description if description.lower() != name.lower() else ""
        purpose = purpose if len(purpose) <= PURPOSE_LIMIT else purpose[:PURPOSE_LIMIT - 1].rstrip() + "…"
        if rule_lookup.catalog_scope(item) == "local":
            purpose = (purpose + " " if purpose else "") + LOCAL_MARK
        seen[name] = purpose
    return [f"{name}: {seen[name]}" if seen[name] else name for name in sorted(seen, key=str.lower)]


@mcp.tool()
def list_rules_compact(ctx: Context | None = None) -> dict:
    """
    Purpose:
        The rules of the catalog that are tagged for discovery, as one short line each (name: purpose), to pick the rules a requirement needs. It is a third the size of get_rules_summary and
        carries what picking needs; it has no descriptions and no READMEs. Read-only.

    After picking:
        Call find_rule_by_name for each rule you pick: it returns the rule's description, application types, inputs, outputs and README. A rule that is not listed here may still exist (only
        tagged rules are listed): find_rule_by_name also looks at the whole catalog and the tenant.

    Returns:
        count and rules (one `Name: purpose` line per rule), or error.
    """
    try:
        rules = rule.fetch_rules_api(ctx=ctx)
    except Exception as e:
        return {"error": f"Could not read the rule catalog: {e}"}
    if not isinstance(rules, list):
        return {"error": f"Could not read the rule catalog: {rules}"}
    lines = index_lines(rules)
    return {"count": len(lines), "rules": "\n".join(lines)}
