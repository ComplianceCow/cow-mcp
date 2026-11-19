"""The compliance logic of the checks in a plan, reported by the orchestrator as a structure the page can draw: the fields a check looks at, the
settings a person can change, and the cases it tries in order with the verdict each gives. Nothing is stored or computed here: the page reads the
structure from the arguments of this call. What this does is refuse a structure that could not be drawn, naming what is wrong, so the caller fixes it."""
from __future__ import annotations

import re
from typing import Any

from fastmcp import Context

from mcpconfig.config import mcp

IDENT = re.compile(r"^[a-z][a-z0-9_-]{0,39}$")
TIME = re.compile(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?$")
FIELD_KINDS = {"text", "number", "time", "flag"}
SETTING_KINDS = {"number", "text"}
UNITS = {"minute", "hour", "day", "week"}
VERDICTS = {"COMPLIANT", "NON_COMPLIANT", "NOT_APPLICABLE"}
LEVELS = {"L1", "L2", "L3"}
OPS = {"equals", "not_equals", "in", "not_in", "greater_than", "at_least", "less_than", "at_most", "missing", "present", "is_true", "is_false"}
ORDERING = {"greater_than", "at_least", "less_than", "at_most"}
MAX_CHECKS, MAX_FIELDS, MAX_SETTINGS, MAX_CASES, MAX_SAMPLES, MAX_LEAVES, MAX_DEPTH, MAX_COLUMNS = 12, 12, 6, 12, 6, 40, 6, 40


def _issue(check: str, path: str, message: str) -> dict:
    return {"check": check, "path": path, "message": message}


def _text(value: Any, limit: int) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= limit


def _time(value: Any) -> bool:
    return isinstance(value, str) and TIME.match(value) is not None


def _literal(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


class _Check:
    """One check being validated: what it declares, and the issues found in it."""

    def __init__(self, check: dict, index: int):
        self.raw = check
        self.name = check.get("id") if isinstance(check.get("id"), str) else f"checks[{index}]"
        self.issues: list[dict] = []
        self.fields: dict[str, str] = {}
        self.settings: dict[str, str] = {}
        self.leaves = 0

    def bad(self, path: str, message: str) -> None:
        self.issues.append(_issue(self.name, path, message))

    # ── fields and settings
    def declare(self) -> None:
        fields = self.raw.get("fields", [])
        if not isinstance(fields, list) or len(fields) > MAX_FIELDS:
            self.bad("fields", f"fields is a list of at most {MAX_FIELDS}")
            fields = []
        for i, f in enumerate(fields):
            p = f"fields[{i}]"
            if not isinstance(f, dict):
                self.bad(p, "a field is an object")
                continue
            fid = f.get("id")
            if not isinstance(fid, str) or not IDENT.match(fid):
                self.bad(f"{p}.id", "a field id is lower case letters, digits, - or _, starting with a letter")
                continue
            if fid in self.fields:
                self.bad(f"{p}.id", f"the field id '{fid}' is used twice")
            kind = f.get("kind")
            if kind not in FIELD_KINDS:
                self.bad(f"{p}.kind", f"kind is one of {sorted(FIELD_KINDS)}")
                continue
            if not _text(f.get("label"), 80):
                self.bad(f"{p}.label", "a field needs a short label a person would use")
            options = f.get("options")
            if options is not None and (kind != "text" or not isinstance(options, list) or len(options) > 12 or not all(isinstance(o, str) and 0 < len(o) <= 60 for o in options)):
                self.bad(f"{p}.options", "options are a list of at most 12 short texts, and only for a text field")
            for extra in ("from", "column"):
                if f.get(extra) is not None and not _text(f.get(extra), 80):
                    self.bad(f"{p}.{extra}", f"{extra} is a short text")
            self.fields[fid] = kind
        settings = self.raw.get("settings", [])
        if not isinstance(settings, list) or len(settings) > MAX_SETTINGS:
            self.bad("settings", f"settings is a list of at most {MAX_SETTINGS}")
            settings = []
        for i, s in enumerate(settings):
            p = f"settings[{i}]"
            if not isinstance(s, dict):
                self.bad(p, "a setting is an object")
                continue
            sid = s.get("id")
            if not isinstance(sid, str) or not IDENT.match(sid):
                self.bad(f"{p}.id", "a setting id is lower case letters, digits, - or _, starting with a letter")
                continue
            if sid in self.settings or sid in self.fields:
                self.bad(f"{p}.id", f"the id '{sid}' is already used by a field or a setting")
            kind = s.get("kind")
            if kind not in SETTING_KINDS:
                self.bad(f"{p}.kind", f"kind is one of {sorted(SETTING_KINDS)}")
                continue
            if not _text(s.get("label"), 80):
                self.bad(f"{p}.label", "a setting needs a label a person would use")
            default = s.get("default")
            if default is not None and not (isinstance(default, (int, float)) and not isinstance(default, bool) if kind == "number" else isinstance(default, str)):
                self.bad(f"{p}.default", f"the default of a {kind} setting is a {kind}")
            if s.get("unit") is not None and s.get("unit") not in UNITS:
                self.bad(f"{p}.unit", f"unit is one of {sorted(UNITS)}")
            self.settings[sid] = kind

    def columns(self) -> None:
        columns = self.raw.get("columns", [])
        if not isinstance(columns, list) or len(columns) > MAX_COLUMNS:
            self.bad("columns", f"columns is a list of at most {MAX_COLUMNS}")
            return
        seen: set[str] = set()
        for i, col in enumerate(columns):
            p = f"columns[{i}]"
            if not isinstance(col, dict) or set(col) - {"name", "kind", "from", "about"}:
                self.bad(p, "a column has name, kind, and optionally from and about")
                continue
            if not _text(col.get("name"), 80):
                self.bad(f"{p}.name", "name is the column's name in the evidence")
            elif col["name"] in seen:
                self.bad(f"{p}.name", f"the column '{col['name']}' is listed twice")
            else:
                seen.add(col["name"])
            if col.get("kind") not in FIELD_KINDS:
                self.bad(f"{p}.kind", f"kind is one of {sorted(FIELD_KINDS)}")
            for extra, limit in (("from", 80), ("about", 160)):
                if col.get(extra) is not None and not _text(col.get(extra), limit):
                    self.bad(f"{p}.{extra}", f"{extra} is a short text")

    # ── conditions
    def condition(self, c: Any, path: str, depth: int = 0) -> None:
        if depth > MAX_DEPTH:
            self.bad(path, f"conditions are nested at most {MAX_DEPTH} deep")
            return
        if not isinstance(c, dict):
            self.bad(path, "a condition is an object")
            return
        groups = [k for k in ("all", "any", "not") if k in c]
        if groups:
            if len(groups) > 1 or len(c) > 1:
                self.bad(path, "a group has exactly one of all, any or not, and nothing else")
                return
            key = groups[0]
            if key == "not":
                self.condition(c["not"], f"{path}.not", depth + 1)
                return
            items = c[key]
            if not isinstance(items, list) or not 1 <= len(items) <= 12:
                self.bad(f"{path}.{key}", f"{key} is a list of 1 to 12 conditions")
                return
            for i, item in enumerate(items):
                self.condition(item, f"{path}.{key}[{i}]", depth + 1)
            return
        self.leaf(c, path)

    def leaf(self, c: dict, path: str) -> None:
        self.leaves += 1
        unknown = set(c) - {"field", "is", "value", "values", "than"}
        if unknown:
            self.bad(path, f"a condition has field, is and then value, values or than; not {sorted(unknown)}")
            return
        field, op = c.get("field"), c.get("is")
        if field not in self.fields:
            self.bad(f"{path}.field", f"'{field}' is not a field of this check: declare it under fields")
            return
        if op not in OPS:
            self.bad(f"{path}.is", f"is is one of {sorted(OPS)}")
            return
        kind = self.fields[field]
        if op in ("missing", "present"):
            if len(c) > 2:
                self.bad(path, f"{op} takes no value")
            return
        if op in ("is_true", "is_false"):
            if kind != "flag" or len(c) > 2:
                self.bad(path, f"{op} is for a flag field and takes no value")
            return
        if kind == "flag" and op in ORDERING:
            self.bad(f"{path}.is", "a flag is compared with is_true or is_false")
            return
        if kind == "text" and op in ORDERING:
            self.bad(f"{path}.is", "a text field is compared with equals, not_equals, in or not_in")
            return
        if op in ("in", "not_in"):
            values = c.get("values")
            if not isinstance(values, list) or not 1 <= len(values) <= 20 or not all(_literal(v) and v is not None for v in values) or "value" in c or "than" in c:
                self.bad(f"{path}.values", "in and not_in take values: a list of 1 to 20 values")
            elif kind == "time" and not all(_time(v) for v in values):
                self.bad(f"{path}.values", "a time is written like 2026-01-31T09:00:00Z")
            return
        has = [k for k in ("value", "than") if k in c]
        if len(has) != 1 or "values" in c:
            self.bad(path, f"{op} takes exactly one of value or than")
            return
        if "value" in has:
            v = c["value"]
            if not _literal(v) or v is None:
                self.bad(f"{path}.value", "a value is a text, a number or true or false")
            elif kind == "number" and not (isinstance(v, (int, float)) and not isinstance(v, bool)):
                self.bad(f"{path}.value", f"'{field}' is a number field: compare it with a number")
            elif kind == "text" and not isinstance(v, str):
                self.bad(f"{path}.value", f"'{field}' is a text field: compare it with a text")
            elif kind == "flag" and not isinstance(v, bool):
                self.bad(f"{path}.value", f"'{field}' is a flag field: compare it with true or false, or use is_true or is_false")
            elif kind == "time" and not _time(v):
                self.bad(f"{path}.value", f"'{field}' is a time field: compare it with another time, now, or a time written like 2026-01-31T09:00:00Z")
            return
        self.operand(c["than"], f"{path}.than", kind)

    def duration(self, d: Any, path: str) -> None:
        if not isinstance(d, dict) or set(d) - {"amount", "unit"}:
            self.bad(path, "a duration is an object with amount and unit")
            return
        amount = d.get("amount")
        if isinstance(amount, dict):
            if set(amount) != {"setting"} or self.settings.get(amount.get("setting")) != "number":
                self.bad(f"{path}.amount", "an amount from a setting is {\"setting\": id} naming a number setting")
        elif not (isinstance(amount, (int, float)) and not isinstance(amount, bool)):
            self.bad(f"{path}.amount", "an amount is a number, or {\"setting\": id}")
        if d.get("unit") not in UNITS:
            self.bad(f"{path}.unit", f"unit is one of {sorted(UNITS)}")

    def operand(self, o: Any, path: str, against: str) -> None:
        if not isinstance(o, dict):
            self.bad(path, "than is an object")
            return
        if "setting" in o:
            if set(o) != {"setting"} or self.settings.get(o["setting"]) != "number" or against != "number":
                self.bad(path, "than {\"setting\": id} names a number setting and is for a number field")
            return
        if "value" in o:
            if set(o) != {"value"} or not _literal(o["value"]) or o["value"] is None:
                self.bad(path, "than {\"value\": ...} holds a text, a number or true or false")
            elif against == "time" and not _time(o["value"]):
                self.bad(path, "a time is written like 2026-01-31T09:00:00Z")
            return
        if "now" in o:
            extra = set(o) - {"now", "plus", "minus"}
            if o["now"] is not True or extra or against != "time":
                self.bad(path, "than {\"now\": true} is for a time field and may add plus or minus")
                return
            for k in ("plus", "minus"):
                if k in o:
                    self.duration(o[k], f"{path}.{k}")
            return
        if "field" in o:
            extra = set(o) - {"field", "plus", "minus"}
            f = o["field"]
            if extra or f not in self.fields:
                self.bad(path, f"than {{\"field\": id}} names a field of this check, with plus or minus for a time")
                return
            if self.fields[f] != against:
                self.bad(path, f"'{f}' is a {self.fields[f]} field and is compared with a {against} field")
            if ("plus" in o or "minus" in o) and self.fields[f] != "time":
                self.bad(path, "plus and minus are for a time field")
            for k in ("plus", "minus"):
                if k in o:
                    self.duration(o[k], f"{path}.{k}")
            return
        self.bad(path, "than is {\"value\": ...}, {\"setting\": id}, {\"field\": id} or {\"now\": true}")

    # ── the rest
    def cases(self) -> None:
        cases = self.raw.get("cases")
        if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
            self.bad("cases", f"cases is a list of 1 to {MAX_CASES}, tried in order")
            return
        for i, case in enumerate(cases):
            p = f"cases[{i}]"
            if not isinstance(case, dict) or set(case) - {"when", "verdict", "code", "reason"}:
                self.bad(p, "a case has when, verdict, code and reason")
                continue
            if "when" in case:
                self.condition(case["when"], f"{p}.when")
            elif i != len(cases) - 1:
                self.bad(p, "only the last case may have no when: it is the 'otherwise' case")
            if case.get("verdict") not in VERDICTS:
                self.bad(f"{p}.verdict", f"verdict is one of {sorted(VERDICTS)}")
            if case.get("code") is not None and not _text(case.get("code"), 60):
                self.bad(f"{p}.code", "code is a short text")
            if case.get("reason") is not None and not _text(case.get("reason"), 300):
                self.bad(f"{p}.reason", "reason is a sentence of at most 300 characters")
        if self.leaves > MAX_LEAVES:
            self.bad("cases", f"a check has at most {MAX_LEAVES} separate conditions: split it or simplify")

    def samples(self) -> None:
        samples = self.raw.get("samples", [])
        if not isinstance(samples, list) or len(samples) > MAX_SAMPLES:
            self.bad("samples", f"samples is a list of at most {MAX_SAMPLES}")
            return
        for i, s in enumerate(samples):
            p = f"samples[{i}]"
            if not isinstance(s, dict) or set(s) - {"label", "values"} or not _text(s.get("label"), 100) or not isinstance(s.get("values"), dict):
                self.bad(p, "a sample has a label and values: {field id: value}")
                continue
            for fid, v in s["values"].items():
                kind = self.fields.get(fid)
                if kind is None:
                    self.bad(f"{p}.values.{fid}", f"'{fid}' is not a field of this check")
                elif v is not None and not (
                    (kind == "text" and isinstance(v, str)) or (kind == "number" and isinstance(v, (int, float)) and not isinstance(v, bool)) or (kind == "flag" and isinstance(v, bool)) or (kind == "time" and _time(v))
                ):
                    self.bad(f"{p}.values.{fid}", f"the value does not fit a {kind} field (a time is written like 2026-01-31T09:00:00Z)")

    def run(self) -> list[dict]:
        raw = self.raw
        if not isinstance(raw.get("id"), str) or not IDENT.match(raw["id"]):
            self.bad("id", "a check id is lower case letters, digits, - or _, starting with a letter")
        if not _text(raw.get("title"), 120):
            self.bad("title", "a check needs a short title a person would use")
        if not _text(raw.get("about"), 400):
            self.bad("about", "about is one or two sentences saying what the check establishes")
        if raw.get("level") is not None and raw.get("level") not in LEVELS:
            self.bad("level", f"level is one of {sorted(LEVELS)}")
        for extra in ("step", "control"):
            if raw.get(extra) is not None and not _text(raw.get(extra), 160):
                self.bad(extra, f"{extra} is the name as the plan writes it")
        unknown = set(raw) - {"id", "title", "about", "level", "step", "control", "fields", "settings", "columns", "applies_to", "cases", "samples"}
        if unknown:
            self.bad("", f"unknown keys: {sorted(unknown)}")
        self.declare()
        self.columns()
        if "applies_to" in raw:
            self.condition(raw["applies_to"], "applies_to")
        self.cases()
        self.samples()
        return self.issues


def validate_checks(checks: Any) -> list[dict]:
    """What is wrong with the structure, as a list of {check, path, message}; empty when it can be drawn."""
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        return [_issue("", "checks", f"checks is a list of 1 to {MAX_CHECKS} checks")]
    issues: list[dict] = []
    seen: set[str] = set()
    for i, check in enumerate(checks):
        if not isinstance(check, dict):
            issues.append(_issue(f"checks[{i}]", "", "a check is an object"))
            continue
        issues += _Check(check, i).run()
        cid = check.get("id")
        if isinstance(cid, str):
            if cid in seen:
                issues.append(_issue(cid, "id", f"the check id '{cid}' is used twice"))
            seen.add(cid)
    return issues


@mcp.tool()
async def compliance_logic(checks: list[dict], ctx: Context | None = None) -> dict:
    """
    Purpose:
        Report how each check of the plan decides compliance, as a structure the page draws as an interactive truth table: the person changes the values and the
        settings and sees which case fits and what verdict it gives. Call it ONCE, with every check that gives a verdict, before you present the plan. You work the
        logic out from the requirement, the design and the READMEs of the rules: nothing here reads SQL. Describe what the check really decides; never invent a rule.
        When you do not know how a catalog rule decides, leave that check out. A test on a value that is missing is neither true nor false, so a case it decides
        does not fit (use missing or present to handle a missing value on purpose). Nothing is stored or changed. The call only checks the structure and tells you
        what to fix.

    Inputs:
        checks: 1 to 12 checks. Each check is:
          id: lower case letters, digits, - or _ (for example "mfa-reconciliation"); the same for every field and setting id: "last-login" or "last_login", never "lastLogin"
          title: a short name a person would use ("MFA reconciliation")
          about: one or two sentences: what the check establishes
          level: "L1", "L2" or "L3" (optional); step: the plan step it belongs to, as the plan writes it (optional); control: the control it sits on (optional)
          fields: what the check looks at, each {id, label, kind: "text"|"number"|"time"|"flag", options: [texts the logic compares with] (text only),
              from: the evidence it comes from, column: the evidence column}
          settings: what a person can change, each {id, label, kind: "number"|"text", default, unit: "minute"|"hour"|"day"|"week"}
          columns: ALWAYS fill this in when you know the evidence's columns: the columns of the evidence the check reads that its logic does not use (yet), so a
              person can bring one in, up to 40 (for example the email, the user type or a created date next to the ones the check tests), each
              {name: the column's name, kind: "text"|"number"|"time"|"flag", from: the evidence it is in, about: what it holds}. List only columns you know from the
              rule's README, the design or a run; never guess one.
          applies_to: a condition that picks the records checked; every other record is skipped (optional)
          cases: 1 to 12, TRIED IN ORDER, the first whose `when` fits gives the result; the last may omit `when` (otherwise). Each {when, verdict:
              "COMPLIANT"|"NON_COMPLIANT"|"NOT_APPLICABLE", code, reason}
          samples: up to 6 worked examples {label, values: {field id: value}}; a time is written 2026-01-31T09:00:00Z (optional)
        A condition is {"all": [...]}, {"any": [...]}, {"not": ...} or a test {"field": id, "is": op, ...}:
          op equals / not_equals / greater_than / at_least / less_than / at_most with "value": ... or "than": operand; in / not_in with "values": [...];
          missing / present; is_true / is_false (flag fields).
          operand: {"value": ...}, {"setting": id}, {"field": id}, {"field": id, "plus": duration}, {"now": true, "minus": duration};
          duration: {"amount": number or {"setting": id}, "unit": "hour"}.

    Example (a user who is not enrolled in MFA is compliant for the first N days):
        {"id": "mfa", "title": "MFA enrolment", "about": "Every active user has enrolled in MFA, unless they joined recently.",
         "fields": [{"id": "status", "label": "User status", "kind": "text", "options": ["ACTIVE", "SUSPENDED"]},
                    {"id": "mfa", "label": "Enrolled in MFA", "kind": "flag"}, {"id": "created", "label": "Account created", "kind": "time"}],
         "settings": [{"id": "grace", "label": "Days a new user has to enrol", "kind": "number", "default": 7, "unit": "day"}],
         "cases": [{"when": {"field": "status", "is": "not_equals", "value": "ACTIVE"}, "verdict": "NOT_APPLICABLE", "reason": "Only active users need MFA"},
                   {"when": {"field": "mfa", "is": "is_true"}, "verdict": "COMPLIANT", "reason": "The user has enrolled"},
                   {"when": {"field": "created", "is": "greater_than", "than": {"now": true, "minus": {"amount": {"setting": "grace"}, "unit": "day"}}},
                    "verdict": "COMPLIANT", "reason": "New user, still inside the enrolment period"},
                   {"verdict": "NON_COMPLIANT", "reason": "An active user past the enrolment period has not enrolled"}]}

    Returns:
        success, the number of checks, and issues (each {check, path, message}). With issues, fix every one and call again.
    """
    issues = validate_checks(checks)
    if issues:
        return {"success": False, "issues": issues, "fix": "the structure could not be drawn: fix each issue named and call compliance_logic again with all the checks"}
    return {"success": True, "checks": len(checks)}
