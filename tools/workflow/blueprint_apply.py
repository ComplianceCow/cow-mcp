"""Rebinds a workflow blueprint to a new use case by changing only what it is told to change: the name, listed text replacements, the ids of the
workflows it starts, and the uploaded files. Everything else in the definition stays exactly as the blueprint has it."""
from __future__ import annotations

import copy
import json
from typing import Any

import yaml

from tools.workflow import blueprint_inspect

PROTECTED_KEYS = {"id", "type"}
MAX_PATHS = 5


def to_yaml(doc: dict) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1_000_000, default_flow_style=False)


def _replace_in(node: Any, old: str, new: str, path: str, found: list[str]) -> Any:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in PROTECTED_KEYS and isinstance(value, str):
                continue
            node[key] = _replace_in(value, old, new, f"{path}.{key}" if path else str(key), found)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            node[index] = _replace_in(value, old, new, f"{path}[{index}]", found)
    elif isinstance(node, str) and old in node:
        found.extend([path] * node.count(old))
        return node.replace(old, new)
    return node


def _replacements(doc: dict, replacements: list[dict], problems: list[str]) -> list[dict]:
    done = []
    for item in replacements:
        old, new = item.get("from"), item.get("to")
        if not isinstance(old, str) or not old or not isinstance(new, str):
            problems.append(f"a replacement needs a non-empty 'from' and a 'to' (text): {item!r}")
            continue
        found: list[str] = []
        _replace_in(doc, old, new, "", found)
        if not found and not item.get("optional"):
            problems.append(f"'{old[:80]}' does not appear in the workflow, so there is nothing to replace")
        done.append({"from": old, "to": new, "count": len(found), "paths": sorted(set(found))[:MAX_PATHS]})
    return done


def _children(doc: dict, children: dict[str, dict], problems: list[str]) -> tuple[list[dict], list[dict]]:
    done, pending, used = [], [], set()
    for _, label, node in blueprint_inspect.nodes(doc.get("spec") or {}):
        action = node.get("action") or {}
        if action.get("type") != "Workflow":
            continue
        reference = action.setdefault("reference", {})
        wanted = reference.get("name")
        given = children.get(wanted)
        if given is None:
            pending.append({"activity": label, "workflow": wanted})
            continue
        used.add(wanted)
        child_id = given.get("id")
        if not isinstance(child_id, str) or not child_id.strip():
            problems.append(f"the id given for '{wanted}' is empty")
            continue
        was = reference.get("id")
        reference["id"] = child_id
        for key in ("name", "displayable"):
            if given.get(key):
                reference[key] = given[key]
        done.append({"activity": label, "workflow": wanted, "id": child_id, "was": was, "name": reference.get("name")})
    for extra in sorted(set(children) - used):
        problems.append(f"this workflow does not start '{extra}'")
    return done, pending


def _files(doc: dict, files: list[dict], problems: list[str]) -> list[dict]:
    done = []
    spec = doc.get("spec") or {}
    for item in files:
        label, input_name, value = item.get("activity"), item.get("input"), item.get("value")
        node = next((n for _, l, n in blueprint_inspect.nodes(spec) if l == label), None)
        target = next((i for i in blueprint_inspect.inputs_of(node) if i.get("name") == input_name), None) if node else None
        if target is None:
            problems.append(f"there is no input '{input_name}' on '{label}'")
        elif str(target.get("type", "")).lower() != "file" or "mapValueFrom" in target:
            problems.append(f"'{input_name}' on '{label}' is not a file input that takes an uploaded file (it is not a file, or it is taken from an earlier step)")
        elif not isinstance(value, str) or not value.strip():
            problems.append(f"the hash for '{input_name}' on '{label}' is empty")
        else:
            target["value"] = value
            if item.get("fileName"):
                target["fileName"] = item["fileName"]
            done.append({"activity": label, "input": input_name, "fileName": target.get("fileName"), "value": value})
    return done


def _typed(item: dict, value: Any) -> tuple[str | None, str | None]:
    """The value as the platform stores it for this input's type, or the reason it does not fit."""
    kind = str(item.get("type", "")).lower()
    if kind == "boolean":
        if isinstance(value, bool):
            return str(value).lower(), None
        text = str(value).strip().lower()
        return (text, None) if text in ("true", "false") else (None, "must be true or false")
    if kind == "number":
        try:
            number = float(str(value).strip())
        except ValueError:
            return None, "must be a number"
        return (str(int(number)) if number == int(number) else str(number)), None
    if kind == "dropdown" and isinstance(item.get("options"), str):
        allowed = [o.strip() for o in item["options"].split(",")]
        return (str(value), None) if str(value) in allowed else (None, f"must be one of {', '.join(allowed)}")
    if kind == "textarray" and isinstance(value, list):
        return ",".join(str(v) for v in value), None
    if isinstance(value, (dict, list, bool)) or value is None:
        return None, "must be text"
    return str(value), None


def _set_inputs(doc: dict, items: list[dict], problems: list[str]) -> list[dict]:
    done = []
    for item in items:
        label, input_name = item.get("activity"), item.get("input")
        node = next((n for _, l, n in blueprint_inspect.nodes(doc.get("spec") or {}) if l == label), None)
        target = next((i for i in blueprint_inspect.inputs_of(node) if i.get("name") == input_name), None) if node else None
        where = f"'{input_name}' on '{label}'"
        if "value" not in item:
            problems.append(f"no value was given for {where}")
        elif target is None:
            problems.append(f"there is no input {where}")
        elif "mapValueFrom" in target:
            problems.append(f"{where} gets its value from another step and cannot be set")
        elif str(target.get("type", "")).lower() == "file":
            problems.append(f"{where} is a file: give it with files")
        else:
            value, why = _typed(target, item["value"])
            if why:
                problems.append(f"the value for {where} {why}")
            else:
                done.append({"activity": label, "input": input_name, "type": target.get("type"), "was": target.get("value"), "value": value})
                target["value"] = value
    return done


def bind_events(doc: dict, tenant_events: list[dict]) -> list[dict]:
    """Points every custom event the workflow uses at the tenant's own event of that name. A custom event is data of one tenant: its id is not the id the
    blueprint carries, and a workflow holding the wrong id shows the event as a pre-built one instead of the custom event."""
    mine = {e["displayable"]: e for e in tenant_events if e.get("type") == "CUSTOM_EVENT" and e.get("id")}
    rebound: dict[tuple[str, str, str], int] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            event = mine.get(node.get("displayable")) if node.get("type") == "CUSTOM_EVENT" else None
            if event:
                if node.get("id") != event["id"]:
                    key = (event["displayable"], str(node.get("id")), event["id"])
                    rebound[key] = rebound.get(key, 0) + 1
                    node["id"] = event["id"]
                if event.get("categoryId"):
                    node["categoryId"] = event["categoryId"]
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(doc)
    return [{"event": name, "was": was, "now": now, "places": count} for (name, was, now), count in sorted(rebound.items())]


def undecided_inputs(unset: list[dict], kept: list[dict] | None, problems: list[str]) -> list[dict]:
    """The required inputs that are still empty and that nobody decided to keep empty: `kept` is [{"rule", "input", "reason"}] (optionally with "activity" to cover only that
    one). The ones with the same rule and input are one entry."""
    covering = []
    for item in kept or []:
        if not isinstance(item, dict) or not item.get("rule") or not item.get("input"):
            problems.append("kept_inputs: each entry needs a rule and an input")
        elif not str(item.get("reason") or "").strip():
            problems.append(f"kept_inputs: say why '{item['input']}' of '{item['rule']}' stays empty")
        else:
            covering.append(item)
    grouped: dict[tuple, dict] = {}
    for entry in unset:
        if any(k["rule"] == entry["rule"] and k["input"] == entry["input"] and k.get("activity") in (None, entry["activity"]) for k in covering):
            continue
        group = grouped.setdefault((entry["rule"], entry["input"]), {"rule": entry["rule"], "input": entry["input"], "type": entry["type"], "settable": entry["settable"],
                                                                      "desc": entry["desc"], "activities": []})
        group["activities"].append(entry["activity"])
    return list(grouped.values())


def apply(doc: dict, new_name: str | None = None, replacements: list[dict] | None = None, children: dict[str, dict] | None = None,
          files: list[dict] | None = None, keep_files: list[str] | None = None, set_inputs: list[dict] | None = None, kept_inputs: list[dict] | None = None) -> dict:
    out = copy.deepcopy(doc)
    problems: list[str] = []
    replaced = _replacements(out, replacements or [], problems)
    started, pending = _children(out, children or {}, problems)
    uploaded = _files(out, files or [], problems)
    inputs_set = _set_inputs(out, set_inputs or [], problems)
    if new_name:
        out.setdefault("metadata", {})["name"] = new_name

    handled = {(f["activity"], f["input"]) for f in uploaded} | {
        (f["activity"], f["input"]) for f in blueprint_inspect.fixed_files(out.get("spec") or {}) if f["activity"] in (keep_files or [])
    }
    unresolved = [
        {"activity": f["activity"], "input": f["input"], "fileName": f["fileName"]}
        for f in blueprint_inspect.fixed_files(out.get("spec") or {})
        if (f["activity"], f["input"]) not in handled
    ]

    unset = blueprint_inspect.required_inputs_unset(out.get("spec") or {})
    undecided = undecided_inputs(unset, kept_inputs, problems) if kept_inputs is not None else []
    problems.extend(
        f"required input '{u['input']}' of the rule '{u['rule']}' is empty on {len(u['activities'])} activit{'y' if len(u['activities']) == 1 else 'ies'} and nobody decided it: "
        + ("set it with set_inputs, " if u["settable"] else "upload its file with files, ")
        + "or keep it empty on purpose with kept_inputs [{\"rule\": ..., \"input\": ..., \"reason\": ...}]"
        for u in undecided
    )

    text = json.dumps(out, ensure_ascii=False)
    stale = sorted({s["was"] for s in started if s["was"] and s["was"] != s["id"] and s["was"] in text})
    problems.extend(f"the blueprint's own id {i} is still in the workflow" for i in stale)
    leftovers = [r["from"] for r in replaced if r["count"] and r["from"] not in r["to"] and r["from"] in text]
    return {
        "doc": out,
        "name": (out.get("metadata") or {}).get("name"),
        "replacements": replaced,
        "workflowsStarted": started,
        "files": uploaded,
        "inputsSet": inputs_set,
        "problems": problems,
        "pendingChildren": pending,
        "unresolvedFiles": unresolved,
        "requiredInputsUnset": unset,
        "requiredInputsUndecided": undecided,
        "mappingIssues": blueprint_inspect.mapping_issues(out.get("spec") or {}),
        "assessmentInputsRead": blueprint_inspect.assessment_inputs_read(out.get("spec") or {}),
        "leftovers": leftovers,
        "ready": not (problems or pending or unresolved or leftovers),
    }
