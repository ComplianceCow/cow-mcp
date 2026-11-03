"""Pushes a use-case YAML into the Playbook graph through the graph loader, once a person has approved exactly what is pushed.

The catalog is global: a use case loaded here is seen by every tenant, and the tools that write to it are not given to unattended runs. So
nothing is sent to the load route until the caller passes back the approval code of the preview it was shown. The code is a hash of the YAML,
the file name and whether an existing version is being replaced, so what was approved is what is sent, and a changed document needs a new
preview. A preview, and its code, is only given for a document the backend's validate route has accepted: that route writes nothing.

Whether the document is a valid use case is the backend's to say. The checks here only make sure that what is sent looks like a use case at
all, and the answers come back whole, so the errors the backend lists can be fixed.
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import yaml

MAX_BYTES = 1_000_000
API_VERSION_PREFIX = "playbook.compliancecow.io/"
_SOURCE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}\.ya?ml$")
_ANSWER_LIMIT = 6000

Post = Callable[[dict], Awaitable[tuple[int | None, Any, str | None]]]


@dataclass(frozen=True)
class Prepared:
    source_name: str
    replace: bool
    data: bytes
    doc: dict


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def prepare(yaml_text: Any, source_name: Any = None, replace: Any = False) -> Prepared:
    """Reads the YAML far enough to say it is a use case. Raises ValueError, with a message the caller can act on, when it is not."""
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ValueError("yaml_text must be the use case's YAML, as text")
    data = yaml_text.encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ValueError(f"the YAML is {len(data)} bytes, more than the {MAX_BYTES} that can be pushed")
    if not isinstance(replace, bool):
        raise ValueError("replace must be true or false")
    try:
        doc = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"the YAML cannot be read: {str(e).splitlines()[0] if str(e) else 'invalid'}") from None
    if not isinstance(doc, dict):
        raise ValueError("the YAML must be one document with keys at the top, not a list or a single value")
    if doc.get("kind") != "UseCase":
        raise ValueError(f"kind must be UseCase, not {doc.get('kind')!r}")
    if not _text(doc.get("apiVersion")).startswith(API_VERSION_PREFIX):
        raise ValueError(f"apiVersion must start with {API_VERSION_PREFIX}, not {doc.get('apiVersion')!r}")
    meta, spec = doc.get("metadata"), doc.get("spec")
    if not isinstance(meta, dict) or not _text(meta.get("id")):
        raise ValueError("metadata.id is required")
    if meta.get("version") is None or not str(meta["version"]).strip():
        raise ValueError("metadata.version is required")
    if not isinstance(spec, dict) or not isinstance(spec.get("steps"), list) or not spec["steps"]:
        raise ValueError("spec.steps must be a list with at least one step")

    name = source_name if source_name not in (None, "") else f"{_text(meta['id'])}.yaml"
    if not isinstance(name, str) or not _SOURCE_NAME.fullmatch(name):
        raise ValueError(f"source_name must be a plain file name ending in .yaml or .yml, such as 'servicenow.yaml', not {name!r}")
    return Prepared(source_name=name, replace=replace, data=data, doc=doc)


def approval_of(p: Prepared) -> str:
    h = hashlib.sha256()
    for part in (b"use-case-push", p.source_name.encode(), b"replace" if p.replace else b"keep", p.data):
        h.update(part)
        h.update(b"\x00")
    return h.hexdigest()


def payload_of(p: Prepared, for_push: bool) -> dict:
    """What the backend is sent. Only a push can ask to replace: the validate route takes no such thing."""
    payload: dict[str, Any] = {"source_name": p.source_name, "doc": base64.b64encode(p.data).decode("ascii")}
    if for_push and p.replace:
        payload["replace"] = True
    return payload


def _clip(body: Any) -> Any:
    if isinstance(body, str):
        return body if len(body) <= _ANSWER_LIMIT else body[:_ANSWER_LIMIT] + "…"
    text = repr(body)
    return body if len(text) <= _ANSWER_LIMIT * 2 else text[:_ANSWER_LIMIT] + "…"


def summary(p: Prepared) -> dict:
    """What a person is shown about the document. Nothing leaves this server to make it."""
    meta, spec = p.doc["metadata"], p.doc["spec"]
    kinds: dict[str, int] = {}
    for step in spec["steps"]:
        kind = step.get("type") if isinstance(step, dict) else None
        kinds[str(kind)] = kinds.get(str(kind), 0) + 1
    return {
        "source_name": p.source_name,
        "id": _text(meta.get("id")),
        "version": str(meta.get("version")),
        "name": spec.get("name"),
        "lifecycle": spec.get("lifecycle"),
        "domainArea": spec.get("domainArea"),
        "steps": len(spec["steps"]),
        "step_types": dict(sorted(kinds.items())),
        "bytes": len(p.data),
        "replace": p.replace,
    }


def validation_of(status_code: int | None, body: Any, problem: str | None = None) -> dict:
    """What the backend's validate route said. valid is True or False only when the backend said so; None means it could not be
    established, which is never taken for valid."""
    if problem:
        return {"valid": None, "problem": problem}
    if not isinstance(body, dict) or "status" not in body:
        return {"valid": None, "http_status": status_code, "backend": _clip(body),
                "problem": "the backend answered in a form this tool does not know, so the document is not taken for valid"}
    if body.get("status") == "success" and body.get("valid") is True:
        return {"valid": True}
    if body.get("status") == "error":
        out: dict[str, Any] = {"valid": False}
        if isinstance(body.get("errors"), list):
            out["validation_errors"] = _clip(body["errors"])
            out["error_count"] = body.get("error_count", len(body["errors"]))
            out["problem"] = f"the backend found {out['error_count']} problem(s) in the YAML"
        else:
            out["problem"] = body.get("error") or "the backend could not accept the YAML"
        return out
    return {"valid": None, "http_status": status_code, "backend": _clip(body),
            "problem": "the backend's answer is not one this tool knows, so the document is not taken for valid"}


async def validate(p: Prepared, post: Post) -> dict:
    """Asks the backend's validate route about the document. It writes nothing."""
    status_code, body, problem = await post(payload_of(p, False))
    return validation_of(status_code, body, problem)


async def review(p: Prepared, post_validate: Post) -> dict:
    """Step one of a push: what would be pushed, and an approval code, but only for a document the backend has accepted."""
    checked = await validate(p, post_validate)
    out: dict[str, Any] = {"pushed": False, **summary(p), "valid": checked["valid"]}
    if checked["valid"] is True:
        out["needs_approval"] = True
        out["approval"] = approval_of(p)
        out["next"] = ("Show this to the person. Only if they approve, call push_use_case again with the same yaml_text, source_name and replace, "
                       "and this approval. The backend then checks the document again and writes it only if it is valid.")
        if p.replace:
            out["warning"] = "replace is true: if this id and version are already in the catalog they will be overwritten, for every tenant."
        return out
    out["needs_approval"] = False
    out.update({k: v for k, v in checked.items() if k != "valid"})
    out["next"] = ("Fix every listed error in the YAML, then call push_use_case again." if checked["valid"] is False
                   else "The document could not be checked, so no approval is given. Try again later.")
    return out


def outcome_of(status_code: int | None, body: Any, problem: str | None = None) -> dict:
    """The load route's answer, whole. It says what happened in `status` (success, conflict or error), and a write that happened says
    `action: pushed`. Only that decides whether it was pushed; an answer in a form not known here is never taken for a success, whatever
    the HTTP code."""
    if problem:
        return {"pushed": False, "problem": problem}
    out: dict[str, Any] = {"pushed": False, "http_status": status_code}
    if not isinstance(body, dict) or "status" not in body:
        out["problem"] = "the backend answered in a form this tool does not know, so nothing is assumed about whether it was pushed"
        out["backend"] = _clip(body)
        return out
    verdict = body.get("status")
    out["backend"] = _clip(body)
    if verdict == "success":
        if body.get("action") == "pushed":
            out["pushed"] = True
            out["loaded"] = {k: body[k] for k in ("key", "content_hash", "stats") if k in body}
        else:
            out["problem"] = f"the backend said success but not that it pushed (action {body.get('action')!r}), so nothing is assumed"
    elif verdict == "conflict":
        out["conflict"] = True
        out["problem"] = body.get("error") or "this id and version are already in the catalog"
        out["hint"] = "To overwrite it, ask the person, then preview and push again with replace=true."
    elif verdict == "error":
        out["problem"] = body.get("error") or f"the backend refused it ({body.get('error_type') or 'error'})"
        if isinstance(body.get("errors"), list):
            out["validation_errors"] = _clip(body["errors"])
            out["next"] = "Fix every listed error in the YAML, then preview and ask for approval again."
    else:
        out["problem"] = f"the backend's status {verdict!r} is not one this tool knows"
    return out


async def push(p: Prepared, approval: Any, post: Post) -> dict:
    if approval != approval_of(p):
        return {"pushed": False, "problem": "approval does not match this document: call push_use_case without approval first, show the person its preview, and pass back the approval it gives. A document that changed needs a new preview."}
    status_code, body, problem = await post(payload_of(p, True))
    return outcome_of(status_code, body, problem)
