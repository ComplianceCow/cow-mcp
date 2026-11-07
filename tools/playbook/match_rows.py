"""Shapes the use-case rows of match_use_case: one candidate per use case, its steps nested."""
from __future__ import annotations

from typing import Any

USE_CASE_FIELDS = ("version", "name", "description", "inScope", "outOfScope", "blockingInputs", "levels")


def group_by_use_case(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The query returns one row per use-case step, so every field of the use case repeats once per step. Return one row per use case, with the
    use-case fields once and the steps (detail, config, requiresApplication) in `steps`; `stepCount` is their number."""
    grouped: dict[Any, dict[str, Any]] = {}
    for row in rows:
        candidate = grouped.setdefault(row.get("id"), {"id": row.get("id"), "steps": []})
        for field in USE_CASE_FIELDS:
            if candidate.get(field) is None and row.get(field) is not None:
                candidate[field] = row[field]
        if row.get("detail") is not None or row.get("config") is not None:
            candidate["steps"].append({"detail": row.get("detail"), "config": row.get("config"), "requiresApplication": row.get("requiresApplication")})
    for candidate in grouped.values():
        for field in USE_CASE_FIELDS:
            candidate.setdefault(field, None)
        candidate["stepCount"] = len(candidate["steps"])
    return list(grouped.values())
