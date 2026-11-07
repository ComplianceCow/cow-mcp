"""Reads a workflow blueprint and reports what has to be rebound before it is created in a tenant: the workflows it starts, the values that
belong to the blueprint's original use case, and the file inputs that carry a template. It never changes the blueprint."""
from __future__ import annotations

import re
from typing import Any


MAX_HITS_PER_NEEDLE = 50
LITERAL_LIMIT = 120
FILE_DESC_MIN = 60

_QUOTED = re.compile(r'"([^"]*)"|\'([^\']*)\'')
_REFERENCE = re.compile(r"\{\{.*?\}\}")
_TEMPLATE_WORD = re.compile(r"template|sample|example|structure", re.IGNORECASE)


def nodes(spec: dict) -> list[tuple[str, str, dict]]:
    """The activities and conditions of a workflow as (kind, label, node)."""
    found = []
    for kind in ("activities", "conditions"):
        for label, node in (spec.get(kind) or {}).items():
            if isinstance(node, dict):
                found.append((kind, label, node))
    return found


def action_of(node: dict) -> dict:
    return node.get("action") or {}


def inputs_of(node: dict) -> list[dict]:
    return [i for i in (action_of(node).get("reference") or {}).get("inputs") or [] if isinstance(i, dict)]


def is_literal(item: dict) -> bool:
    return "value" in item and "mapValueFrom" not in item


def _clip(value: Any, limit: int = LITERAL_LIMIT) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "..."


def literals_in(expression: str) -> list[str]:
    """The quoted strings of an expression, leaving out the {{ }} references that are filled in at run time."""
    cleaned = _REFERENCE.sub("", expression or "")
    return [a or b for a, b in _QUOTED.findall(cleaned) if (a or b)]


def triggers(spec: dict) -> list[dict]:
    found = []
    for transition in spec.get("transitions") or []:
        if transition.get("type") != "Event":
            continue
        event = transition.get("event") or {}
        specinput = event.get("specInput") or {}
        expr = specinput.get("expr")
        found.append({
            "from": transition.get("from"),
            "to": transition.get("to"),
            "event": event.get("displayable"),
            "eventId": event.get("id"),
            "eventType": event.get("type"),
            "specInput": specinput or None,
            "literals": literals_in(expr) if isinstance(expr, str) else [],
            "desc": event.get("desc"),
            "payload": [{"name": p.get("name"), "type": p.get("type"), "desc": p.get("desc")} for p in event.get("payload") or []],
        })
    return found


def children(spec: dict) -> list[dict]:
    found = []
    for _, label, node in nodes(spec):
        action = action_of(node)
        if action.get("type") != "Workflow":
            continue
        reference = action.get("reference") or {}
        found.append({
            "activity": label,
            "name": reference.get("name"),
            "id": reference.get("id"),
            "eventName": reference.get("eventName"),
            "async": bool(action.get("asyncActionExecution")),
            "inputs": [
                {
                    "name": i.get("name"),
                    "type": i.get("type"),
                    "desc": i.get("desc"),
                    "from": ((i.get("mapValueFrom") or {}).get("source") or {}).get("label"),
                    "outputField": (i.get("mapValueFrom") or {}).get("outputField"),
                }
                for i in inputs_of(node)
            ],
        })
    return found


def fixed_files(spec: dict) -> list[dict]:
    """File inputs holding uploaded content (a hash) instead of the output of an earlier node."""
    found = []
    for _, label, node in nodes(spec):
        for item in inputs_of(node):
            if item.get("type") == "File" and is_literal(item) and item.get("value"):
                found.append({
                    "activity": label,
                    "input": item.get("name"),
                    "fileName": item.get("fileName"),
                    "value": item.get("value"),
                    "desc": item.get("desc"),
                    "activityDesc": action_of(node).get("desc"),
                })
    return found


def templates(spec: dict) -> list[dict]:
    """Descriptions that carry a structure the user's file has to follow: a sample in the node's description, or an input description that gives a sample, or a file's that says more than its name."""
    found = []
    for _, label, node in nodes(spec):
        node_desc = action_of(node).get("desc")
        if isinstance(node_desc, str) and "{" in node_desc:
            found.append({"activity": label, "source": "activity", "desc": node_desc})
        for item in inputs_of(node):
            desc = item.get("desc")
            if "mapValueFrom" in item or not isinstance(desc, str):
                continue
            if "{" in desc or _TEMPLATE_WORD.search(desc) or (str(item.get("type", "")).lower() == "file" and len(desc) > FILE_DESC_MIN):
                found.append({"activity": label, "source": "input", "input": item.get("name"), "type": item.get("type"), "desc": desc})
    return found


def needs(spec: dict) -> dict:
    """What a workflow needs the tenant to have: its start events, the rules and functions its activities run."""
    events = {}
    for t in triggers(spec):
        if t["event"]:
            events.setdefault(t["event"], {"displayable": t["event"], "type": t["eventType"], "id": t["eventId"]})
    rules, functions = {}, {}
    for _, _, node in nodes(spec):
        action = action_of(node)
        reference = action.get("reference") or {}
        if action.get("type") == "Rule" and reference.get("name"):
            rules.setdefault(reference["name"], {"name": reference["name"], "id": reference.get("id"), "appScope": reference.get("appScopeName")})
        elif action.get("type") == "Function" and reference.get("name"):
            functions.setdefault(reference["name"], {"name": reference["name"], "id": reference.get("id"), "displayable": reference.get("displayable")})
    return {"events": list(events.values()), "rules": list(rules.values()), "functions": list(functions.values())}


def input_details(spec: dict, labels: list[str]) -> tuple[list[dict], list[str]]:
    """Every input of the named activities and conditions, so a value can be chosen from what each input says it is."""
    wanted = {label: None for label in labels}
    found = []
    for kind, label, node in nodes(spec):
        if label not in wanted:
            continue
        wanted[label] = True
        action = action_of(node)
        found.append({
            "activity": label,
            "kind": "activity" if kind == "activities" else "condition",
            "type": action.get("type"),
            "desc": action.get("desc") or (action.get("reference") or {}).get("desc"),
            "inputs": [
                {
                    "name": i.get("name"),
                    "type": i.get("type"),
                    "desc": i.get("desc"),
                    "options": i.get("options"),
                    "optional": bool(i.get("optional")),
                    "value": _clip(i["value"]) if "value" in i else None,
                    "mappedFrom": ((i.get("mapValueFrom") or {}).get("source") or {}).get("label"),
                    "settable": "mapValueFrom" not in i and str(i.get("type", "")).lower() != "file",
                }
                for i in inputs_of(node)
            ],
        })
    return found, sorted(label for label, hit in wanted.items() if not hit)


def app_scopes(spec: dict) -> list[str]:
    names = {(action_of(n).get("reference") or {}).get("appScopeName") for _, _, n in nodes(spec)}
    return sorted(n for n in names if n)


def condition_literals(spec: dict) -> list[dict]:
    found = []
    for label, node in (spec.get("conditions") or {}).items():
        expr = action_of(node).get("expr") if isinstance(node, dict) else None
        values = literals_in(expr) if isinstance(expr, str) else []
        if values:
            found.append({"condition": label, "expr": expr, "literals": values})
    return found


def literal_inputs(spec: dict) -> list[dict]:
    return [
        {"activity": label, "input": i.get("name"), "type": i.get("type"), "value": _clip(i.get("value"))}
        for _, label, node in nodes(spec)
        for i in inputs_of(node)
        if is_literal(i)
    ]


def occurrences(doc: Any, needles: list[str]) -> dict[str, dict]:
    """Where each string appears in any value of the blueprint, so a name changed on the fly is changed everywhere."""
    hits: dict[str, list[dict]] = {n: [] for n in needles}
    totals = {n: 0 for n in needles}

    def walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")
        elif isinstance(node, str):
            for needle in needles:
                at = node.find(needle)
                if at < 0:
                    continue
                totals[needle] += node.count(needle)
                if len(hits[needle]) < MAX_HITS_PER_NEEDLE:
                    hits[needle].append({"path": path, "snippet": node[max(0, at - 40): at + len(needle) + 40]})

    walk(doc, "")
    return {n: {"count": totals[n], "where": hits[n]} for n in needles}


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def required_inputs_unset(spec: dict) -> list[dict]:
    """The inputs a rule or function needs (not optional) that hold no value, no uploaded file and no mapping from an earlier node, so nothing would supply them
    when the workflow runs. A rule may fill some of them with a default of its own (its log or config files); this lists them so each is decided, not to say each is wrong."""
    found = []
    for kind, label, node in nodes(spec):
        reference = action_of(node).get("reference") or {}
        for item in inputs_of(node):
            if item.get("optional") or "mapValueFrom" in item:
                continue
            if not _empty(item.get("value")) or item.get("fileName") or item.get("fileContent") or item.get("fileAttachments"):
                continue
            found.append({
                "activity": label,
                "kind": "activity" if kind == "activities" else "condition",
                "rule": reference.get("name"),
                "input": item.get("name"),
                "type": item.get("type"),
                "desc": _clip(item.get("desc") or "", 160),
                "settable": str(item.get("type", "")).lower() != "file",
            })
    return found


def assessment_inputs_read(spec: dict) -> list[dict]:
    """The activities that read an assessment input (the rule FetchAssessmentInput): its name (the literal value of `InputName`, None when it is taken from an earlier
    step) and the activity's description when that carries a sample of the content, so what the assessment must be given is known without reading every activity."""
    found = []
    for _, label, node in nodes(spec):
        action = action_of(node)
        reference = action.get("reference") or {}
        if reference.get("name") != "FetchAssessmentInput":
            continue
        name_input = next((i for i in inputs_of(node) if i.get("name") == "InputName"), None) or {}
        name = name_input.get("value") if is_literal(name_input) and not _empty(name_input.get("value")) else None
        desc = (action.get("desc") or reference.get("desc") or "").strip()
        found.append({"activity": label, "inputName": name, "sample": desc if len(desc) >= FILE_DESC_MIN else None})
    return found


def chain_assessment_inputs(workflows: dict[str, dict]) -> list[dict]:
    """The assessment inputs the whole chain reads, one entry per name, with every workflow and activity that reads it and the first sample found."""
    merged: dict[Any, dict] = {}
    for workflow, report in workflows.items():
        for item in report.get("assessmentInputsRead") or []:
            entry = merged.setdefault(item["inputName"] or (workflow, item["activity"]), {"inputName": item["inputName"], "readBy": [], "sample": None})
            entry["readBy"].append({"workflow": workflow, "activity": item["activity"]})
            entry["sample"] = entry["sample"] or item["sample"]
    return list(merged.values())


def mapping_issues(spec: dict) -> list[dict]:
    """Inputs taken from an earlier node whose source cannot supply them: an activity that is not in the workflow, an output field the source does not declare, or an event mapping
    with no field named. Such an input is accepted when the workflow is created and fails or runs empty when it runs."""
    found = []
    labelled = {label: node for _, label, node in nodes(spec)}
    for _, label, node in nodes(spec):
        for item in inputs_of(node):
            mapping = item.get("mapValueFrom")
            if not isinstance(mapping, dict):
                continue
            source = (mapping.get("source") or {}).get("label") or (mapping.get("source") or {}).get("displayable")
            field = mapping.get("outputField")
            problem = None
            if mapping.get("type") == "Activity":
                if source not in labelled:
                    problem = f"its source activity '{source}' is not in this workflow"
                else:
                    declared = [o.get("name") for o in (action_of(labelled[source]).get("reference") or {}).get("outputs") or [] if isinstance(o, dict)]
                    if field and declared and field not in declared:
                        problem = f"'{source}' has no output '{field}'"
            elif mapping.get("type") == "Event" and not field:
                problem = f"it is taken from the event '{source}' without naming the field of the event"
            if problem:
                found.append({"activity": label, "input": item.get("name"), "problem": problem})
    return found


def inspect(doc: dict, find: list[str] | None = None, include_literals: bool = False, activities: list[str] | None = None) -> dict:
    spec = doc.get("spec") or {}
    metadata = doc.get("metadata") or {}
    literal = literal_inputs(spec)
    report = {
        "name": metadata.get("name"),
        "description": metadata.get("description"),
        "triggers": triggers(spec),
        "workflows": children(spec),
        "fixedFiles": fixed_files(spec),
        "templates": templates(spec),
        "appScopes": app_scopes(spec),
        "rules": sorted(r["name"] for r in needs(spec)["rules"]),
        "conditionLiterals": condition_literals(spec),
        "literalInputCount": len(literal),
        "requiredInputsUnset": required_inputs_unset(spec),
        "mappingIssues": mapping_issues(spec),
        "assessmentInputsRead": assessment_inputs_read(spec),
    }
    if include_literals:
        report["literalInputs"] = literal
    if find:
        report["occurrences"] = occurrences(doc, find)
    if activities:
        report["inputDetails"], report["unknownActivities"] = input_details(spec, activities)
    return report


def chain_of(root: dict, library: dict[str, dict]) -> dict:
    """The workflows a blueprint starts, directly or through other workflows, in the order they have to be created: the ones that start nothing first.
    `library` holds every workflow of the blueprint by name."""
    order: list[str] = []
    missing: list[str] = []
    cycle: list[str] = []

    def visit(name: str, trail: list[str]) -> None:
        if name in order or cycle:
            return
        if name in trail:
            cycle.extend(trail[trail.index(name):] + [name])
            return
        doc = library.get(name)
        if doc is None:
            missing.append(name)
            return
        for child in children(doc.get("spec") or {}):
            if child["name"]:
                visit(child["name"], trail + [name])
        order.append(name)

    visit((root.get("metadata") or {}).get("name"), [])
    return {"order": order, "missing": sorted(set(missing)), "cycle": cycle}


def library_of(entry: dict) -> tuple[dict | None, dict[str, dict]]:
    """The root workflow of one blueprint and all of its workflows by name. A blueprint is a folder: its own definition under `config`, and the
    workflows it starts under `config.subworkflow`, keyed by file name rather than by workflow name."""
    config = entry.get("config") if isinstance(entry, dict) else None
    if not isinstance(config, dict) or not isinstance(config.get("spec"), dict):
        return None, {}
    root = {k: v for k, v in config.items() if k != "subworkflow"}
    library = {}
    for definition in [root, *(config.get("subworkflow") or {}).values()]:
        name = (definition.get("metadata") or {}).get("name") if isinstance(definition, dict) else None
        if name:
            library[name] = definition
    return root, library


def blueprint_named(output: Any, name: str) -> dict | None:
    """The blueprint folder called exactly `name`, out of what the blueprint call returned (`items` keyed by folder name)."""
    items = output.get("items") if isinstance(output, dict) else None
    entry = items.get(name) if isinstance(items, dict) else None
    return entry if isinstance(entry, dict) else None


def names_in(output: Any) -> list[str]:
    items = output.get("items") if isinstance(output, dict) else None
    return sorted(items) if isinstance(items, dict) else []


DESCRIPTION_LIMIT = 400


def summarize_listing(output: Any, search: str | None = None) -> list[dict]:
    """One short row per blueprint folder from a `fields=basic` listing, optionally only those that contain every word of `search` (case-insensitive)
    in the folder name, the workflow name or the description."""
    items = output.get("items") if isinstance(output, dict) else None
    if not isinstance(items, dict):
        return []
    rows = []
    for folder, entry in sorted(items.items()):
        entry = entry if isinstance(entry, dict) else {}
        config = (entry.get("config") or {}).get("metadata") or {}
        others = [(entry.get(k) or {}).get("metadata") or {} for k in ("spec", "binding")]
        description = config.get("description") or next((m["description"] for m in others if m.get("description")), None)
        rows.append({
            "folder": folder,
            "workflow": config.get("name"),
            "description": _clip(description, DESCRIPTION_LIMIT) if description else None,
            "hasDefinition": isinstance(entry.get("config"), dict),
        })
    words = (search or "").lower().split()
    return [r for r in rows if all(w in " ".join(str(r[k] or "") for k in ("folder", "workflow", "description")).lower() for w in words)]


BRIEF_OMITTED = ("templates", "assessmentInputsRead")


def brief(report: dict) -> dict:
    """The inspection without the parts only the person who creates the workflow needs: each workflow's `templates` and `assessmentInputsRead`,
    and the `sample` text of every assessment input (the structure a file must follow). The chain, the prerequisites, the application scopes and
    the inputs still to be set stay."""
    out = dict(report)
    out["workflows"] = {name: {k: v for k, v in detail.items() if k not in BRIEF_OMITTED} for name, detail in (report.get("workflows") or {}).items()}
    if "assessmentInputs" in out:
        out["assessmentInputs"] = [{k: v for k, v in item.items() if k != "sample"} for item in out["assessmentInputs"]]
    out["brief"] = "templates, assessmentInputsRead and the samples of assessmentInputs are left out: call again without brief to get them (needed when the workflow is created)"
    return out
