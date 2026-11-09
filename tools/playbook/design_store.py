"""Keeps each design that passed check_use_case_design under an id, so the YAML is written once (in the check call) and read by id afterwards."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import yaml


def directory() -> Path:
    return Path(os.environ.get("COW_MCP_DESIGN_DIR") or Path.home() / ".cache" / "cow-mcp" / "designs")


def design_id(yaml_text: str) -> str | None:
    """A short id from the content of the design (the same design always has the same id), or None when the text is not YAML."""
    try:
        canonical = json.dumps(yaml.safe_load(yaml_text), sort_keys=True, default=str)
    except yaml.YAMLError:
        return None
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]


def save(yaml_text: str, domain: str | None, check_arguments: dict[str, Any] | None = None) -> str | None:
    did = design_id(yaml_text)
    if did is None:
        return None
    folder = directory()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{did}.yaml").write_text(yaml_text)
    meta = {"domain": domain, "savedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "checkArguments": check_arguments or {}}
    (folder / f"{did}.json").write_text(json.dumps(meta, default=str))
    return did


def load(did: str, domain: str | None) -> tuple[str, dict] | None:
    """The stored YAML and its metadata, or None when there is no such design for this tenant."""
    if not did or not did.isalnum():
        return None
    folder = directory()
    try:
        meta = json.loads((folder / f"{did}.json").read_text())
        text = (folder / f"{did}.yaml").read_text()
    except (OSError, ValueError):
        return None
    if meta.get("domain") != domain:
        return None
    return text, meta


def outline(doc: dict) -> list[dict]:
    return [{"id": s.get("id"), "type": s.get("type"), "level": s.get("level"), "name": s.get("name"), "prerequisiteSteps": s.get("prerequisiteSteps") or []}
            for s in ((doc.get("spec") or {}).get("steps") or []) if isinstance(s, dict)]


def read(did: str, domain: str | None, step_ids: list[str] | None = None) -> dict:
    """What get_design returns: the whole YAML (no step_ids) or just those steps, always with the outline."""
    found = load(did, domain)
    if found is None:
        return {"success": False, "error": f"No design '{did}' for this tenant. Use the id returned by a valid check_use_case_design call."}
    text, meta = found
    doc = yaml.safe_load(text)
    out: dict[str, Any] = {"success": True, "designId": did, "savedAt": meta.get("savedAt"), "name": (doc.get("spec") or {}).get("name"), "outline": outline(doc)}
    if step_ids:
        wanted = {str(i) for i in step_ids}
        steps = [s for s in ((doc.get("spec") or {}).get("steps") or []) if isinstance(s, dict) and str(s.get("id")) in wanted]
        out["steps"] = steps
        out["missing"] = sorted(wanted - {str(s.get("id")) for s in steps})
        out["inputs"] = (doc.get("spec") or {}).get("inputs") or {}
    else:
        out["yaml"] = text
    return out
