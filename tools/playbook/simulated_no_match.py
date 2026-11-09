"""Test hook: while a lease file is valid, the matcher tools answer as if the catalog held nothing for a requirement, so the no-match design path can be exercised."""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path


# TEMPORARY (agreed with the user): while True, the matcher tools behave as if the catalog held no use case at all, for every requirement.
# Revert by setting it to False (or `git checkout tools/playbook/simulated_no_match.py tools/playbook/usecasematcher.py`) and restarting the MCP server.
FORCE_NO_MATCH = False


def lease_path() -> Path:
    return Path(os.environ.get("COW_MCP_NO_MATCH_LEASE") or Path.home() / ".cache" / "cow-mcp" / "simulate_no_match.json")


def _lease() -> dict | None:
    try:
        lease = json.loads(lease_path().read_text())
        return lease if float(lease["until"]) > time.time() else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def active(utterance: str) -> bool:
    """True only while the lease has not expired and the utterance matches every keyword (regex, case-insensitive) in it."""
    if FORCE_NO_MATCH:
        return True
    lease = _lease()
    keywords = [str(k) for k in (lease or {}).get("keywords") or []]
    return bool(keywords) and all(re.search(k, utterance or "", re.I) for k in keywords)


def hidden(use_case_id: str | None) -> bool:
    """True while the lease has not expired and names this use case in `hide`: the catalog then answers as if it did not hold it."""
    if FORCE_NO_MATCH:
        return True
    return str(use_case_id) in [str(i) for i in (_lease() or {}).get("hide") or []]
