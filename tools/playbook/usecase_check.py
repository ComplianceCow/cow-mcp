"""Checks a use-case YAML against the rules the designer recipe states and that can be decided from the document alone, so a missed rule is reported instead of
trusted. It reads nothing from the platform and writes nothing."""
from __future__ import annotations

import re
from typing import Any

import yaml
from fastmcp import Context

from mcpconfig.config import mcp

FIRST_KEYS = ["System", "Source", "ResourceID", "ResourceName", "ResourceType", "ResourceLocation", "ResourceTags"]
LAST_KEYS = ["ValidationStatusCode", "ValidationStatusNotes", "ComplianceStatus", "ComplianceStatusReason", "EvaluatedTime", "UserAction", "ActionStatus", "ActionResponseURL"]
REMEDIATION = ("create_action", "create_workflow")


def _issue(severity: str, check: str, message: str, step: str | None = None) -> dict:
    return {"severity": severity, "check": check, "step": step, "message": message}


def parse(yaml_text: str) -> tuple[Any, dict | None]:
    try:
        return yaml.safe_load(yaml_text), None
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" (line {mark.line + 1}, column {mark.column + 1})" if mark else ""
        problem = getattr(e, "problem", None) or str(e)
        hint = " A value that contains ': ' or starts with a special character must be in quotes, or written as a block (`>`)." if "mapping values are not allowed" in str(e) or "expected" in problem else ""
        return None, _issue("error", "yaml", f"the text is not valid YAML{where}: {problem}.{hint}")


def _mask(sql: str) -> str:
    """The SQL with comments and quoted text blanked out (same length), so keywords and commas are only found where they mean something."""
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(" " * (j - i)); i = j
        elif c in "'\"":
            j = i + 1
            while j < n:
                if sql[j] == c:
                    if j + 1 < n and sql[j + 1] == c:
                        j += 2
                        continue
                    break
                j += 1
            out.append(c + " " * (min(j, n - 1) - i - 1) + (c if j < n else "")); i = min(j + 1, n)
        else:
            out.append(c); i += 1
    return "".join(out)[:n].ljust(n)


def _blank_comments(sql: str) -> str:
    """The SQL with its comments replaced by spaces, leaving quoted text as it is."""
    out, i, n, quote = [], 0, len(sql), None
    while i < n:
        c = sql[i]
        if quote:
            out.append(c)
            if c == quote:
                quote = None
            i += 1
        elif c in "'\"":
            quote = c; out.append(c); i += 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i); j = n if j < 0 else j
            out.append(" " * (j - i)); i = j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2); j = n if j < 0 else j + 2
            out.append(" " * (j - i)); i = j
        else:
            out.append(c); i += 1
    return "".join(out)


def _depths(mask: str) -> list[int]:
    depth, found = 0, []
    for c in mask:
        if c == ")":
            depth -= 1
        found.append(depth)
        if c == "(":
            depth += 1
    return found


_SET_OPERATOR = re.compile(r"\b(UNION|INTERSECT|EXCEPT|MINUS)\b", re.I)
_NOT_AN_ALIAS = {"END", "NULL", "TRUE", "FALSE", "ASC", "DESC", "DAY", "MONTH", "YEAR", "HOUR", "MINUTE", "SECOND"}
_BEFORE_AN_OPERAND = {"AND", "OR", "NOT", "IS", "IN", "LIKE", "ILIKE", "THEN", "ELSE", "WHEN", "BETWEEN", "ON", "CASE", "DISTINCT", "INTERVAL"}
_IDENTIFIER = r"\"[^\"]+\"|`[^`]+`|[A-Za-z_]\w*"


def _unquote(name: str) -> str:
    return name[1:-1] if len(name) > 1 and name[0] in "\"`" and name[-1] == name[0] else name


def _alias_without_as(piece: str) -> str | None:
    """`w.ResourceName ResourceName` or `'x' Source`: an expression followed by a name, with no AS. Not taken for one when the last word is a keyword (END, NULL) or the
    expression ends with an operator or a keyword that expects an operand (`a AND b`, `a + b`)."""
    found = re.fullmatch(rf"(?s)(.*\S)\s+({_IDENTIFIER})", piece)
    if not found:
        return None
    expression, name = found.groups()
    if name.upper() in _NOT_AN_ALIAS or expression[-1] in "+-*/%|&<>=!,(.:":
        return None
    last_word = re.search(r"([A-Za-z_]\w*)$", expression)
    if last_word and last_word.group(1).upper() in _BEFORE_AN_OPERAND:
        return None
    return _unquote(name)


def select_list(sql: str) -> dict:
    """The output columns of the first SELECT of the statement (a UNION takes its column names from its first SELECT; a WITH query's final SELECT is the first one outside the
    parentheses): {"items": [{name, bare, text}], "star": bool, "from": upstream table or None, "setOperation": bool}, or {"error": why} when it cannot be read.
    An item's name is None when no name can be told (an expression with no alias)."""
    sql = _blank_comments(sql)
    mask = _mask(sql)
    depths = _depths(mask)
    selects = [m.start() for m in re.finditer(r"\bSELECT\b", mask, re.I) if depths[m.start()] == 0]
    if not selects:
        return {"error": "no SELECT at the top level"}
    start = selects[0] + len("SELECT")
    from_at = next((m.start() for m in re.finditer(r"\bFROM\b", mask[start:], re.I) if depths[start + m.start()] == 0), None)
    set_at = next((m.start() for m in _SET_OPERATOR.finditer(mask[start:]) if depths[start + m.start()] == 0), None)
    if set_at is not None and (from_at is None or set_at < from_at):
        from_at = None
    end = start + (from_at if from_at is not None else set_at if set_at is not None else len(sql) - start)
    body, body_mask, body_depths = sql[start:end], mask[start:end], depths[start:end]
    body = re.sub(r"^\s*DISTINCT\b", "", body, flags=re.I)
    body_mask = re.sub(r"^\s*DISTINCT\b", lambda m: " " * len(m.group(0)), body_mask, flags=re.I)

    pieces, last = [], 0
    for i, c in enumerate(body_mask):
        if c == "," and body_depths[i] == 0:
            pieces.append(body[last:i]); last = i + 1
    pieces.append(body[last:])

    items, star = [], False
    for piece in (p.strip() for p in pieces):
        if not piece:
            continue
        if re.fullmatch(r"(\w+\.)?\*", piece):
            star = True
            continue
        alias = re.search(rf"\bAS\s+({_IDENTIFIER})\s*$", piece, re.I)
        bare = re.fullmatch(r"(?:\w+\.)?\"?([A-Za-z_]\w*)\"?", piece)
        if alias:
            items.append({"name": _unquote(alias.group(1)), "bare": False, "text": piece})
        elif bare:
            items.append({"name": bare.group(1), "bare": True, "text": piece})
        else:
            items.append({"name": _alias_without_as(piece), "bare": False, "text": piece})
    table = None
    if from_at is not None:
        m = re.match(r"\s*FROM\s+\"?([A-Za-z_]\w*)\"?", sql[end:], re.I)
        table = m.group(1) if m else None
    return {"items": items, "star": star, "from": table, "setOperation": set_at is not None}


def structure_problems(names: list[str]) -> list[str]:
    """What is wrong with an evidence's column list against the 16 mandatory keys: the first seven first and in order, the last eight last and in order, and anything else only between them."""
    problems = []
    if len(set(names)) != len(names):
        problems.append("a column appears twice: " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
    missing = [k for k in FIRST_KEYS + LAST_KEYS if k not in names]
    if missing:
        problems.append("mandatory keys missing: " + ", ".join(missing))
    first_ok = names[: len(FIRST_KEYS)] == FIRST_KEYS
    last_ok = names[len(names) - len(LAST_KEYS):] == LAST_KEYS if len(names) >= len(LAST_KEYS) else False
    if not missing and not (first_ok and last_ok):
        if not first_ok:
            problems.append(f"the first seven columns must be {', '.join(FIRST_KEYS)} in that order; they are {', '.join(names[:len(FIRST_KEYS)])}")
        if not last_ok:
            problems.append(f"the last eight columns must be {', '.join(LAST_KEYS)} in that order; they are {', '.join(names[-len(LAST_KEYS):])}")
    return problems


def _steps(doc: Any) -> list[dict]:
    steps = ((doc or {}).get("spec") or {}).get("steps") if isinstance(doc, dict) else None
    return [s for s in steps if isinstance(s, dict)] if isinstance(steps, list) else []


def check(doc: Any, remediation_columns: dict[str, list[str]] | None, remediation_confirmed: bool) -> dict:
    issues: list[dict] = []
    steps = _steps(doc)
    if not steps:
        return {"valid": False, "errors": [_issue("error", "structure", "spec.steps is missing or empty")], "warnings": [], "checked": {"steps": 0}}

    by_id: dict[str, dict] = {}
    for s in steps:
        sid = s.get("id")
        if not isinstance(sid, str) or not sid:
            issues.append(_issue("error", "structure", "a step has no id"))
        elif sid in by_id:
            issues.append(_issue("error", "structure", f"the step id '{sid}' is used twice", sid))
        else:
            by_id[sid] = s
        if not s.get("type"):
            issues.append(_issue("error", "structure", "the step has no type", sid if isinstance(sid, str) else None))
    for s in steps:
        for needed in s.get("prerequisiteSteps") or []:
            if needed not in by_id:
                issues.append(_issue("error", "structure", f"prerequisite '{needed}' is not a step of this use case", s.get("id") if isinstance(s.get("id"), str) else None))

    producers: dict[str, dict] = {}
    parsed: dict[str, dict] = {}
    for sid, s in by_id.items():
        config = s.get("config") if isinstance(s.get("config"), dict) else {}
        if s.get("type") == "create_rule" and config.get("evidenceName"):
            producers[str(config["evidenceName"])] = s
        if s.get("type") == "create_rule" and isinstance(config.get("sql"), str):
            parsed[sid] = select_list(config["sql"])

    remediation_steps = [s for s in by_id.values() if s.get("type") in REMEDIATION]
    anchored = {str((s.get("config") or {}).get("evidenceName")): s for s in remediation_steps if (s.get("config") or {}).get("evidenceName")}

    for sid, result in parsed.items():
        evidence = str(by_id[sid]["config"].get("evidenceName") or sid)
        if "error" in result:
            issues.append(_issue("warning", "evidence", f"the SQL of '{evidence}' could not be read ({result['error']}), so its columns were not checked", sid))
            continue
        if result["star"] and not result["items"]:
            if evidence in anchored:
                issues.append(_issue("error", "evidence", f"'{evidence}' triggers {anchored[evidence]['id']} but its SQL is SELECT *: list every output column, with the required ones at position 8", sid))
            continue
        if result["star"]:
            issues.append(_issue("warning", "evidence", f"the SQL of '{evidence}' mixes * with named columns, so its structure was not checked", sid))
            continue
        unnamed = [i["text"] for i in result["items"] if i["name"] is None]
        if unnamed:
            result["unreadable"] = True
            issues.append(_issue("warning", "evidence", f"'{evidence}': no column name could be told for `{unnamed[0][:80]}`, so its columns were not checked; write `AS <ColumnName>` after it", sid))
            continue
        for problem in structure_problems([i["name"] for i in result["items"]]):
            issues.append(_issue("error", "evidence", f"'{evidence}': {problem}", sid))

    columns = remediation_columns or {}
    for step in remediation_steps:
        sid = step.get("id")
        evidence = (step.get("config") or {}).get("evidenceName")
        if not evidence:
            issues.append(_issue("error", "remediation", "the step has no config.evidenceName (the evidence that triggers it)", sid))
            continue
        evidence = str(evidence)
        producer = producers.get(evidence)
        if producer is None:
            issues.append(_issue("error", "remediation", f"no create_rule step writes the evidence '{evidence}'", sid))
        elif producer.get("id") not in (step.get("prerequisiteSteps") or []):
            issues.append(_issue("error", "remediation", f"'{producer.get('id')}' writes '{evidence}' but is not in this step's prerequisiteSteps", sid))
        elif producer.get("level") and step.get("level") and producer["level"] != step["level"]:
            issues.append(_issue("warning", "remediation", f"the step is {step['level']} but '{evidence}' is produced at {producer['level']}", sid))
        if step.get("type") == "create_workflow":
            folder = (step.get("refs") or {}).get("workflow")
            if not isinstance(folder, str) or not folder or re.search(r"\s", folder):
                issues.append(_issue("error", "remediation", "refs.workflow must be the blueprint folder name, a plain id with no spaces", sid))
        if evidence not in columns:
            issues.append(_issue("error", "remediation-columns", f"remediation_columns says nothing about '{evidence}': pass the columns its READMEs require, or an empty list after reading them and finding none", sid))
            continue
        wanted = [str(c) for c in columns[evidence]]
        result = parsed.get(producer["id"]) if producer else None
        if not wanted or result is None or "error" in result or result.get("unreadable") or (result["star"] and not result["items"]):
            continue
        names = [i["name"] for i in result["items"]]
        extras = names[len(FIRST_KEYS): len(names) - len(LAST_KEYS)] if len(names) >= len(FIRST_KEYS) + len(LAST_KEYS) else []
        absent = [c for c in wanted if c not in names]
        misplaced = [c for c in wanted if c in names and c not in extras]
        if absent:
            issues.append(_issue("error", "remediation-columns", f"'{evidence}' does not output the required column(s): {', '.join(absent)}", producer["id"]))
        if misplaced:
            issues.append(_issue("error", "remediation-columns", f"the required column(s) {', '.join(misplaced)} of '{evidence}' are not at position 8 (between ResourceTags and ValidationStatusCode)", producer["id"]))
        upstream = parsed.get(producers[result["from"]]["id"]) if result["from"] in producers else None
        for column in (c for c in wanted if c in extras):
            item = next(i for i in result["items"] if i["name"] == column)
            if not item["bare"]:
                continue
            if upstream and "items" in upstream and not upstream["star"] and column not in [i["name"] for i in upstream["items"]]:
                issues.append(_issue("error", "remediation-columns", f"'{column}' is selected by its bare name but its upstream evidence '{result['from']}' does not have it: select it as an empty literal ('' AS {column}) or take it from a column that exists", producer["id"]))
            elif not upstream:
                issues.append(_issue("warning", "remediation-columns", f"'{column}' is selected by its bare name: the upstream evidence '{result['from']}' must have it, or the SQL fails when the rule runs", producer["id"]))

    produces_findings = any(re.search(r"NON_COMPLIANT", (s.get("config") or {}).get("sql") or "") for s in by_id.values())
    if (remediation_steps or produces_findings) and not remediation_confirmed:
        issues.append(_issue("error", "remediation-decision", "the user has not confirmed the remediation decision (action, workflow, both or none, and the layer of each): ask it in Questions and write the YAML after the answer; 'none' is also the user's answer"))

    errors = [i for i in issues if i["severity"] == "error"]
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": [i for i in issues if i["severity"] == "warning"],
        "checked": {"steps": len(by_id), "rulesWithSql": len(parsed), "remediationSteps": len(remediation_steps)},
    }


@mcp.tool()
async def check_use_case_design(yaml_text: str, remediation_columns: dict[str, list[str]] | None = None, remediation_confirmed_by_user: bool = False, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Check a use-case YAML against the designer's own rules before it is returned: that it parses, that every step has an id and valid prerequisites, that every
        evidence SQL outputs the 16 mandatory keys in order, that every action or workflow is triggered by an evidence a prerequisite rule writes, that each such evidence
        outputs the columns its READMEs require at position 8, and that the user's remediation decision was confirmed. It reads nothing from the platform and writes nothing.
        validate_use_case_yaml (the platform's schema check) is a different check and does not replace this one.

    Inputs:
        yaml_text: the whole use case, as YAML text.
        remediation_columns: {"<evidenceName>": ["<column>", ...]} for the evidence that triggers each action or workflow: the columns its READMEs require, with their exact names.
            An evidence with no required column is given an empty list, and only after its READMEs were read.
        remediation_confirmed_by_user: true only when the user answered the remediation question (including "none") and the layer of each remediation.

    Returns:
        valid, errors, warnings (each: check, step, message) and checked. Fix every error and call again; do not return a YAML with errors.
    """
    doc, problem = parse(yaml_text)
    if problem:
        return {"valid": False, "errors": [problem], "warnings": [], "checked": {"steps": 0}}
    return check(doc, remediation_columns, bool(remediation_confirmed_by_user))
