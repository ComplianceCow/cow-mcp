"""Does a workflow blueprint's trigger fit the assessment the workflow is anchored to? Read from the blueprints' own descriptions, with no blueprint named here."""
from __future__ import annotations

import re
from typing import Any

_TRIGGER = re.compile(r"\bwhen\s+(?:an?|the)\s+(.+?)\s+assessment\s+run\s+(?:completes|is\s+completed|finishes)", re.I)
_LEVEL_TAG = re.compile(r"\(\s*L\d\s*\)", re.I)


def _norm(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _LEVEL_TAG.sub(" ", str(text or "")).lower()).strip()


def trigger_scope(description: Any) -> str | None:
    """The assessment a blueprint's trigger is tied to ("NIST 800-53 v5 (L2)" in "Triggered when a NIST 800-53 v5 (L2) assessment run completes"), or None for a generic trigger
    ("Triggered when an assessment run completes") or a description that says nothing about it."""
    found = _TRIGGER.search(str(description or ""))
    if not found:
        return None
    return found.group(1).strip()


def fits(scope: str | None, anchor: Any) -> bool:
    """A generic trigger fits every assessment; a named one fits only the assessment it names."""
    if scope is None:
        return True
    wanted, got = _norm(scope), _norm(anchor)
    return bool(got) and (wanted == got or wanted in got or got in wanted)


def _words(text: Any) -> set[str]:
    return {w for w in _norm(text).split() if len(w) > 2}


def alternatives(chosen: dict, listing: list[dict]) -> list[str]:
    """The deployable blueprints with a generic trigger whose description is most like the chosen one's: the likeliest replacements."""
    mine = _words(chosen.get("description"))
    scored = []
    for row in listing:
        if row.get("folder") == chosen.get("folder") or not row.get("hasDefinition") or trigger_scope(row.get("description")) is not None:
            continue
        theirs = _words(row.get("description"))
        overlap = len(mine & theirs) / max(1, len(mine | theirs))
        if overlap >= 0.5:
            scored.append((overlap, row["folder"]))
    return [folder for _, folder in sorted(scored, reverse=True)]


def issues(doc: dict, listing: list[dict] | None) -> list[dict]:
    """One error for each workflow step whose blueprint is triggered only by an assessment other than the one the step is anchored to."""
    if not listing:
        return []
    by_folder = {row.get("folder"): row for row in listing if isinstance(row, dict)}
    out = []
    for step in ((doc.get("spec") or {}).get("steps") or []):
        if not isinstance(step, dict) or step.get("type") != "create_workflow":
            continue
        folder = (step.get("refs") or {}).get("workflow")
        row = by_folder.get(folder)
        anchor = (step.get("config") or {}).get("assessmentName")
        scope = trigger_scope((row or {}).get("description"))
        if row is None or fits(scope, anchor):
            continue
        better = alternatives(row, listing)
        advice = f" Use a blueprint with a generic trigger instead, for example {', '.join(better)}." if better else " Use a blueprint whose trigger is not tied to a named assessment (list_workflow_blueprints shows each trigger)."
        out.append({"check": "workflow-blueprint", "step": step.get("id"), "severity": "error",
                    "message": f"the blueprint '{folder}' is triggered only when a '{scope}' assessment run completes, but this workflow is anchored to '{anchor}', so it would never start.{advice}"})
    return out
