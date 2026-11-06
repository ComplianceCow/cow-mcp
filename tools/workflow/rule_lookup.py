"""Answers "does this rule exist, and what does it need" for a rule that was named explicitly, looking at everything the tenant and the rule catalog hold and not
only the rules tagged for discovery."""
from __future__ import annotations

import base64
from typing import Any

from tools.workflow import blueprint_scopes

DISCOVERY_TAG = "MCP"


def _exact(items: Any, name: str, key, prefer=None) -> dict | None:
    if not isinstance(items, list):
        return None
    matches = [i for i in items if isinstance(i, dict) and key(i) == name]
    return next((i for i in matches if prefer and prefer(i)), matches[0] if matches else None)


def _discoverable(item: dict) -> bool:
    return DISCOVERY_TAG in ((item.get("meta") or {}).get("tags") or [])


def _readme(copies: list[dict], preferred: dict | None) -> str | None:
    """The README of the rule, from the preferred copy or else from any other copy that has one."""
    for item in sorted(copies, key=lambda i: i is not preferred):
        encoded = item.get("readmeData")
        if not encoded:
            continue
        try:
            return base64.b64decode(encoded).decode("utf-8", errors="replace")
        except (TypeError, ValueError):
            continue
    return None


def readme_of(name: str, catalog_items: Any) -> str | None:
    """The README of the rule with this exact name among the catalog rows, preferring the copy that discovery lists."""
    copies = [i for i in catalog_items or [] if isinstance(i, dict) and _catalog_name(i) == name]
    return _readme(copies, _exact(catalog_items, name, _catalog_name, prefer=_discoverable))


def _inputs(tenant: dict | None, catalog: dict | None) -> list[dict]:
    """Each input of the rule as {name, type, required}: from the catalog's definition, overridden by the tenant's published one."""
    found: dict[str, dict] = {}
    spec = (catalog or {}).get("spec") or {}
    for meta in spec.get("inputsMeta__") or []:
        found[meta["name"]] = {"name": meta["name"], "type": meta.get("dataType"), "required": bool(meta.get("required"))}
    for name in spec.get("inputs") or {}:
        found.setdefault(name, {"name": name, "type": None, "required": False})
    for item in ((tenant or {}).get("ruleInputs") or {}).values():
        if isinstance(item, dict) and item.get("name"):
            found[item["name"]] = {"name": item["name"], "type": item.get("type"), "required": bool(item.get("isrequired"))}
    return list(found.values())


def _outputs(tenant: dict | None, catalog: dict | None) -> list[dict]:
    """Each output of the rule as {name, type, description}: the names from the catalog's mapping and the tenant, the detail from the catalog's metadata."""
    spec = (catalog or {}).get("spec") or {}
    detail = {m["name"]: m for m in spec.get("outputsMeta__") or [] if isinstance(m, dict) and m.get("name")}
    names = [m.split(":=")[0].removeprefix("*.Output.") for m in spec.get("ioMap") or [] if m.startswith("*.Output.")]
    names += list(detail) + list((tenant or {}).get("ruleOutputs") or {})
    return [{"name": n, "type": detail.get(n, {}).get("dataType"), "description": detail.get(n, {}).get("description")} for n in dict.fromkeys(names)]


def _tenant_name(item: dict) -> Any:
    return item.get("name")


def _catalog_name(item: dict) -> Any:
    return (item.get("meta") or {}).get("name")


def describe(name: str, tenant_items: Any, catalog_items: Any) -> dict:
    """`tenant_items` and `catalog_items` are the rows each listing returned for the name, or None when that lookup failed.

    where: "tenant" (published), "catalog" (known to the rule catalog and published by the platform when a workflow using it is created), "missing" (in
    neither) or "unchecked" (a lookup failed and the rule was not found in the other place)."""
    in_tenant = _exact(tenant_items, name, _tenant_name)
    in_catalog = _exact(catalog_items, name, _catalog_name, prefer=_discoverable)
    copies = [i for i in catalog_items or [] if isinstance(i, dict) and _catalog_name(i) == name]
    if in_tenant is None and in_catalog is None:
        failed = tenant_items is None or catalog_items is None
        return {"success": False, "name": name, "where": "unchecked" if failed else "missing"}

    meta = (in_catalog or {}).get("meta") or {}
    types = blueprint_scopes.rule_app_types(in_catalog) if in_catalog else set()
    if in_tenant and not types:
        tags = in_tenant.get("tags")
        wanted = (tags.get("appType") if isinstance(tags, dict) else None) or []
        types = {blueprint_scopes.normalize(t) for t in (wanted if isinstance(wanted, list) else [wanted])} - {""}
    return {
        "success": True,
        "name": name,
        "where": "tenant" if in_tenant else "catalog",
        "purpose": meta.get("purpose"),
        "description": meta.get("description") or (in_tenant or {}).get("description"),
        "appTypes": sorted(types),
        "discoverable": _discoverable(in_catalog) if in_catalog else None,
        "inputs": _inputs(in_tenant, in_catalog),
        "outputs": _outputs(in_tenant, in_catalog),
        "readme": _readme(copies, in_catalog),
        "lookupFailed": [place for place, rows in (("tenant", tenant_items), ("catalog", catalog_items)) if rows is None],
    }
