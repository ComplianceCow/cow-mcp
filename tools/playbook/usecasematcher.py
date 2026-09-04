from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from typing import Any
from utils import utils
from utils.debug import logger
from mcpconfig.config import mcp

from constants import constants
from mcptypes import assets_tools_type as vo
from fastmcp import Context


# Match-quality bands. Deliberately conservative: a wrong "full match" is the one
# unrecoverable failure, so the gap between FULL and PARTIAL is wide.
FULL_MATCH = float(os.environ.get("PLAYBOOK_FULL_MATCH", "0.55"))
PARTIAL_MATCH = float(os.environ.get("PLAYBOOK_PARTIAL_MATCH", "0.25"))

# LLM_MATCH: hand the candidate list to the calling agent instead of scoring it
# here. The lexical/vector path stays the default — this only replaces it when
# explicitly turned on, so existing deployments see no behavior change.
LLM_MATCH = os.environ.get("PLAYBOOK_LLM_MATCH", "1").strip().lower() in \
    {"1", "true", "yes", "on"}


async def q(
    cypher: str,
    ctx: Context | None = None,
    **params,
) -> list[dict]:
    """Execute a Playbook query through the cowgraphloader API."""
    payload = {
        "query": cypher,
        "parameters": params,
    }

    response = await utils.make_API_call_to_CCow_v2(
        payload,
        constants.URL_PLAYBOOK_FETCH_DATA,
        ctx=ctx,
    )

    if isinstance(response, str):
        raise RuntimeError(response)

    if "error" in response:
        raise RuntimeError(response["error"])

    return response.get("data", [])


async def w(
    cypher: str,
    ctx: Context | None = None,
    **params,
) -> list[dict]:
    """Execute a Playbook write through the cowgraphloader API."""
    return await q(cypher, ctx=ctx, **params)

# ── matching ─────────────────────────────────────────────────────────────────

STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "do", "does",
    "did", "not", "no", "who", "what", "which", "that", "this", "these", "those",
    "our", "we", "us", "i", "my", "you", "your", "for", "of", "in", "on", "at",
    "to", "with", "and", "or", "but", "have", "has", "had", "can", "could",
    "would", "should", "all", "any", "some", "it", "its", "how", "me", "show",
}


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t not in STOP and len(t) > 1}


def lexical_score(utterance: str, entries: list[str], description: str = "") -> dict:
    """
    Best single-entry overlap, with a nudge from the description and a
    corroboration requirement before a hit is allowed to reach the FULL band.

    Fallback for when no embeddings are loaded. Deliberately simple so the score
    is explainable: the entry that earned it comes back in `matchedOn`.

    WHY CORROBORATION. `intentPhrases.inScope` carries two kinds of string —
    questions a client would ask ("which managers are missing MFA") and
    capability nouns naming coverage ("AWS IAM users"). A noun is fully contained
    in any utterance that mentions it, so "list our AWS IAM users" scores 1.0
    against an MFA use case that cannot answer it. Requiring a second entry to
    clear PARTIAL before banding FULL costs nothing on a real question — those
    overlap several entries — and demotes a lone noun hit to PARTIAL, where the
    agent composes instead of offering the whole use case.

    It narrows the hole rather than closing it. An utterance that genuinely
    echoes two entries still bands FULL, so `outOfScope` remains the guard that
    has to be read back.
    """
    u = tokens(utterance)
    if not u:
        return {"score": 0.0, "matchedOn": None, "corroborated": False}

    scored = sorted(
        ((len(u & pt) / len(pt), p) for p in (entries or [])
        if (pt := tokens(p))),
        key=lambda x: -x[0],
    )
    top1, matched = scored[0] if scored else (0.0, None)
    top2 = scored[1][0] if len(scored) > 1 else 0.0

    score = top1
    if description and (dt := tokens(description)):
        score = min(1.0, score + 0.15 * (len(u & dt) / len(dt)))

    corroborated = top2 >= PARTIAL_MATCH
    if score >= FULL_MATCH and not corroborated:
        score = FULL_MATCH - 0.001          # demote to PARTIAL, keep it visible

    return {"score": round(score, 3),
            "matchedOn": matched if top1 > 0 else None,
            "corroborated": corroborated}


def embed(text: str) -> list[float]:
    """No provider wired. See load_playbook.py for the two options."""
    raise NotImplementedError("no embedding provider configured")


async def have_vectors(ctx: Context | None = None) -> bool:
    r = await q(
        "MATCH (u:UseCase {isLatest:true}) WHERE u.embedding IS NOT NULL "
        "RETURN count(u) AS c",
        ctx=ctx,
    )
    return bool(r and r[0]["c"])


def band(score: float) -> str:
    return "FULL" if score >= FULL_MATCH else "PARTIAL" if score >= PARTIAL_MATCH else "NONE"


# ── tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def catalog_stats(ctx: Context | None = None) -> dict:
    """
    Size and shape of the catalog. Useful as a connectivity check and to know
    whether vector matching is available, and whether PLAYBOOK_LLM_MATCH has
    handed matching off to the calling agent.
    """
    r = await q("""
        MATCH (u:UseCase {isLatest:true})
        OPTIONAL MATCH (u)-[:HAS_STEP]->(s:UseCaseStep)
        RETURN count(DISTINCT u) AS useCases, count(s) AS steps,
            collect(DISTINCT u.domainArea) AS domains
    """, ctx=ctx)[0]
    gaps = await q("MATCH (r:UseCaseRequest) RETURN count(r) AS c", ctx=ctx)[0]["c"]
    matcher = "llm" if LLM_MATCH else ("vector" if await have_vectors(ctx) else "lexical")
    return {**r, "openGaps": gaps, "matcher": matcher, "database": constants.URL_PLAYBOOK_FETCH_DATA}


@mcp.tool()
async def list_use_cases(domain: str | None = None, lifecycle: str = "published", ctx: Context | None = None) -> list[dict]:
    """
    Browse the catalog. Latest version of each use case only.

    Use this when the client asks what exists rather than describing a problem —
    for a described problem, use match_use_case instead.

    `lifecycle` is the authored state — draft | published | deprecated. Pass null
    for all of them.
    """
    return await q("""
        MATCH (u:UseCase {isLatest:true})
        WHERE ($lifecycle IS NULL OR u.lifecycle = $lifecycle)
        AND ($domain IS NULL OR u.domainArea = $domain OR u.domain = $domain)
        OPTIONAL MATCH (u)-[:HAS_STEP]->(s:UseCaseStep)
        RETURN u.id AS id, u.version AS version, u.name AS name,
            u.domainArea AS domainArea, u.levels AS levels,
            count(s) AS steps, u.blockingInputs AS blockingInputs
        ORDER BY u.name
    """, ctx=ctx, domain=domain, lifecycle=lifecycle)


@mcp.tool()
async def match_use_case(utterance: str, limit: int = 5, ctx: Context | None = None) -> dict:
    """
    Match a user's requirement, expressed in their own words, against the
    ComplianceCow Playbook catalog.

    MANDATORY FIRST TOOL:
    This tool MUST be called first for every requirement-driven request before
    calling any other Playbook, ComplianceCow, workflow, or capability tool.

    Requirement-driven requests include requests for a desired capability,
    outcome, automation, workflow, analysis, data collection, modification,
    compliance-related functionality, or any other request asking whether
    ComplianceCow can perform something.

    Do NOT skip this tool simply because another tool appears to be directly
    related to the user's request.

    This tool only determines catalog coverage and returns candidates. The
    calling agent is responsible for deciding and executing the next step.

    MATCHING RULES:
    - Match the user's actual intent and required outcome, not just keywords.
    - Do not claim FULL based only on a similar use-case name or description.
    - Consider the use case's inScope and outOfScope information.
    - Consider blockingInputs when determining whether the capability can
        satisfy the requested requirement.
    - Do not invent capabilities, integrations, inputs, outputs, or steps that
        are not present in the Playbook catalog.
    - A similar name or keyword does not by itself constitute a match.

    MATCH RESULTS:

    FULL:
    - The existing use case satisfies the user's requested capability.
    - Return the relevant use case and supporting catalog information.
    - The calling agent may continue with the matched use case.
    - Do NOT call match_steps for a straightforward FULL match.
    - Do NOT call record_gap for a FULL match.
    - describe_use_case may be called later if additional details are required.

    PARTIAL:
    - An existing use case provides useful capability but does not completely
        satisfy the user's requirement.
    - Clearly identify the supported and missing capability.
    - A PARTIAL result must never be presented as a complete solution.
    - The calling agent should call match_steps to determine whether reusable
        steps can cover the missing capability.
    - The calling agent should record the remaining gap with record_gap.

    NONE:
    - No existing Playbook use case adequately satisfies the requirement.
    - The calling agent should call record_gap with resolution="no_match".
    - Do not invent a use case or claim that the capability exists.
    - match_steps may be used when existing reusable steps could provide
        useful building blocks despite the absence of a complete use case.

    IMPORTANT — outOfScope:
    - Treat outOfScope as authoritative catalog information.
    - When a candidate has relevant outOfScope information, the calling agent
        must not present the candidate as fully suitable without communicating
        the applicable limitation.
    - Do not invent, reinterpret, or silently omit catalog scope limitations.

    TOOL ORDER:
    For a requirement-driven request:

        match_use_case FIRST
            -> FULL    -> continue with the matched use case
            -> PARTIAL -> match_steps -> record_gap
            -> NONE    -> record_gap
            -> match_steps only if useful

    Do not use list_use_cases as a substitute for match_use_case when the user
    has described a specific requirement.

    LLM MATCHING:
    If PLAYBOOK_LLM_MATCH is enabled, this tool returns candidates without
    computing a lexical or vector score. The calling agent must evaluate the
    candidates using the returned catalog fields and determine FULL, PARTIAL,
    or NONE.

    EXECUTION BOUNDARY:
    This tool only determines coverage against the global Playbook catalog.

    It does not:
    - Execute customer workflows.
    - Inspect tenant infrastructure.
    - Perform live customer-environment assessments.
    - Modify customer resources.
    - Publish or deploy workflows.
    - Claim that a customer's environment is compliant.
    """
    rows = await q("""
        MATCH (u:UseCase {isLatest:true})
        OPTIONAL MATCH (u)-[:HAS_STEP]->(s:UseCaseStep)
        RETURN u.id AS id, u.version AS version, u.name AS name,
            u.description AS description,
            u.inScope AS inScope, u.outOfScope AS outOfScope,
            u.blockingInputs AS blockingInputs, u.levels AS levels,
            count(s) AS steps
    """, ctx=ctx)

    if LLM_MATCH:
        # No score, no threshold, no truncation — the correct candidate must
        # not be cut before the caller ever sees it. Judgment happens on the
        # other side of this call, against these exact fields.
        return {
            "utterance": utterance, "matcher": "llm",
            "guidance": (
                "No score was computed. Weigh each candidate's inScope, "
                "outOfScope, and description against the utterance yourself "
                "and decide FULL, PARTIAL, or NONE per candidate. FULL: read "
                "outOfScope back to the client verbatim before offering it — "
                "a wrong FULL is the one failure this product cannot recover "
                "from. PARTIAL: say what it does and does not cover, then "
                "call match_steps to compose from the parts that fit — pass "
                "the FULL/PARTIAL ids here as match_steps' use_case_ids so "
                "it doesn't re-scan every use case you already ruled out. "
                "NONE on every candidate: call record_gap, then walk the "
                "client through the step vocabulary to author one."
            ),
            "candidates": rows,
        }

    matcher = "lexical"
    if await have_vectors(ctx):
        try:
            vec = embed(utterance)
            hits = {r["id"]: r["score"] for r in await q("""
                CALL db.index.vector.queryNodes('usecase_intent', $k, $v)
                YIELD node AS u, score
                WHERE u.isLatest AND u.lifecycle = 'published'
                RETURN u.id AS id, score
            """, ctx=ctx, k=limit * 2, v=vec)}
            for r in rows:
                r["score"] = round(hits.get(r["id"], 0.0), 3)
                r["matchedOn"] = None
            matcher = "vector"
        except NotImplementedError:
            pass
    if matcher == "lexical":
        for r in rows:
            r.update(lexical_score(utterance, r["inScope"], r["description"]))

    rows.sort(key=lambda r: -r["score"])
    top = [r for r in rows if r["score"] >= PARTIAL_MATCH][:limit]
    for r in top:
        r["match"] = band(r["score"])

    best = band(top[0]["score"]) if top else "NONE"
    guidance = {
        "FULL": "Offer this. State outOfScope verbatim first, then collect blockingInputs.",
        "PARTIAL": "Do not offer this as a whole. Say what it does and does not cover, "
                "then call match_steps to compose from the parts that fit.",
        "NONE": "Nothing in the catalog fits. Call record_gap, then walk the client "
                "through the step vocabulary to author one.",
    }[best]
    return {"utterance": utterance, "matcher": matcher, "bestMatch": best,
            "guidance": guidance, "candidates": top,
            "thresholds": {"full": FULL_MATCH, "partial": PARTIAL_MATCH}}


@mcp.tool()
async def match_steps(utterance: str, limit: int = 8, exclude_use_case: str | None = None,
                use_case_ids: list[str] | None = None, ctx: Context | None = None) -> dict:
    """
    Match individual steps across the catalog.

    This is the compose path, and in practice the most common one — most requests
    are neither a whole match nor a blank page. A client asking for "MFA on
    service accounts, ticket to ServiceNow" can take a create_application step
    from one use case and a ServiceNow create_action step from another, and author
    only the gap.

    Steps returned here can be adapted into a new use case; each carries
    `adaptedFrom` so the composed use case stays explainable.

    `use_case_ids` narrows the search to those use cases only — pass the FULL
    and PARTIAL candidates from match_use_case here rather than searching the
    whole catalog. Omit it to search every use case; on a small catalog that's
    fine, but it stops scaling once match_use_case's NONE candidates outnumber
    its real ones.

    If PLAYBOOK_LLM_MATCH is set, this returns every step in scope unscored —
    weigh `inScope`/`description` against the utterance yourself. Under that
    mode especially, call match_use_case first and pass its FULL/PARTIAL
    candidates as `use_case_ids`: that tool already sent you the base
    description/intent to judge relevance from, so pulling every step in the
    catalog here — rather than just the use cases you already judged worth a
    closer look — repeats work you've done and hands you a pile you don't need.
    """
    rows = await q("""
        MATCH (u:UseCase {isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        WHERE ($exclude IS NULL OR u.id <> $exclude)
        AND ($ids IS NULL OR u.id IN $ids)
        RETURN s.id AS stepId, s.type AS type, s.level AS level,
            s.description AS description, s.inScope AS inScope,
            s.mustAnswer AS mustAnswer,
            u.id AS useCaseId, u.name AS useCaseName
    """, ctx=ctx, exclude=exclude_use_case, ids=use_case_ids)
    for r in rows:
        r["adaptedFrom"] = f"{r['useCaseId']}/{r['stepId']}"

    if LLM_MATCH:
        return {
            "utterance": utterance, "matcher": "llm", "steps": rows,
            "guidance": "No score was computed. Weigh each step's inScope "
                        "and description against the utterance yourself; "
                        "adopt whichever steps genuinely fit.",
            "note": "Steps with mustAnswer fields still need those answers in the "
                    "composed use case — adapting a step does not answer them.",
        }

    for r in rows:
        # A step's intentPhrases are all questions — no capability nouns — so the
        # corroboration cap rarely bites here, and composing from a step is a
        # softer commitment than offering a whole use case in any case.
        r.update(lexical_score(utterance, r["inScope"], r["description"]))
    rows.sort(key=lambda r: -r["score"])
    hits = [r for r in rows if r["score"] >= PARTIAL_MATCH][:limit]
    for r in hits:
        r.pop("inScope", None)
    return {"utterance": utterance, "matcher": "lexical", "steps": hits,
            "note": "Steps with mustAnswer fields still need those answers in the "
                    "composed use case — adapting a step does not answer them."}


@mcp.tool()
async def describe_use_case(use_case_id: str, ctx: Context | None = None) -> dict:
    """
    The full use case in client-facing terms: what it covers, what it does not,
    what the client must decide, and the ordered sequence.

    The order is this use case's own. There is no canonical pipeline — another
    use case declares a different set in a different order, so do not describe
    the sequence as standard.
    """
    head = await q("""
        MATCH (u:UseCase {id:$id, isLatest:true})
        RETURN u.id AS id, u.version AS version, u.name AS name,
            u.description AS description, u.domainArea AS domainArea,
            u.levels AS levels, u.inScope AS inScope, u.outOfScope AS outOfScope,
            u.blockingInputs AS blockingInputs, u.lifecycle AS lifecycle
    """, ctx=ctx, id=use_case_id)
    if not head:
        return {"error": f"no use case {use_case_id!r} — try list_use_cases"}
    steps = await q("""
        MATCH (u:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        OPTIONAL MATCH (s)-[:DEPENDS_ON]->(d:UseCaseStep)
        RETURN s.seq AS seq, s.id AS id, s.type AS type, s.level AS level,
            s.name AS name, s.description AS description,
            s.mustAnswer AS mustAnswer,
            collect(d.id) AS dependsOn
        ORDER BY s.seq
    """, ctx=ctx, id=use_case_id)
    return {**head[0], "steps": steps,
            "note": "Every step listed is declared by this use case; a step absent "
                    "from the list does not exist here rather than being disabled. "
                    "No step is marked optional — whether one can be dropped is "
                    "computed from structure, so ask validate_modifications rather "
                    "than assuming."}


@mcp.tool()
async def explain_step(use_case_id: str, step_id: str, ctx: Context | None = None) -> dict:
    """
    What one step touches, what it needs, and what needs it.

    Use this when a client asks why a step is there, or before proposing to drop
    one — `neededBy` is what breaks if it goes.
    """
    head = await q("""
        MATCH (:UseCase {id:$uc, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep {id:$sid})
        RETURN s.id AS id, s.type AS type, s.level AS level, s.name AS name,
            s.description AS description, s.config AS config,
            s.mustAnswer AS mustAnswer, s.anchorLevel AS anchorLevel,
            s.controlSource AS controlSource,
            s.requiresApplication AS requiresApplication
    """, ctx=ctx, uc=use_case_id, sid=step_id)
    if not head:
        return {"error": f"no step {step_id!r} in {use_case_id!r}"}
    touches = await q("""
        MATCH (:UseCase {id:$uc, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep {id:$sid})
        MATCH (s)-[r]->(t)
        WHERE NOT t:UseCaseStep AND NOT t:UseCase
        RETURN type(r) AS edge, labels(t)[0] AS kind,
            coalesce(t.catalogRef, t.ref, t.name) AS target
        ORDER BY edge
    """, ctx=ctx, uc=use_case_id, sid=step_id)
    deps = await q("""
        MATCH (:UseCase {id:$uc, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep {id:$sid})
        OPTIONAL MATCH (s)-[:DEPENDS_ON]->(d)
        OPTIONAL MATCH (s)<-[:DEPENDS_ON]-(n)
        RETURN collect(DISTINCT d.id) AS dependsOn, collect(DISTINCT n.id) AS neededBy
    """, ctx=ctx, uc=use_case_id, sid=step_id)[0]
    return {**head[0], **deps, "touches": touches}


@mcp.tool()
async def get_modification_surface(use_case_id: str, ctx: Context | None = None) -> dict:
    """
    What a client may change, per step, and what they must answer first.

    `blockingInputs` must be answered before any plan exists, and `inputSchema`
    is the WHOLE modification surface — every value a client may change is an
    input, typed and declared once. A step's `config` shows which of its values
    are wired to an input (`${{ inputs.x }}`) and which are literals fixed by the
    author. A literal is not negotiable without authoring work.

    Dropping is not a third tier and there is no droppable list. No step is
    authored as optional — ask validate_modifications with the specific set the
    client wants gone, and it answers from structure. An author's guess at what is
    droppable can contradict the dependency and schema facts, and did.
    """
    head = await q("""
        MATCH (u:UseCase {id:$id, isLatest:true})
        RETURN u.blockingInputs AS blockingInputs, u.inputs AS inputsJson
    """, ctx=ctx, id=use_case_id)
    if not head:
        return {"error": f"no use case {use_case_id!r}"}
    steps = await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        RETURN s.seq AS seq, s.id AS id, s.type AS type,
            s.mustAnswer AS mustAnswer, s.config AS config
        ORDER BY s.seq
    """, ctx=ctx, id=use_case_id)
    return {
        "useCaseId": use_case_id,
        "blockingInputs": head[0]["blockingInputs"],
        "inputSchema": head[0]["inputsJson"],
        "steps": steps,
        "note": "Rebinding is not supported: a clone may override values and drop "
                "steps, but may not move an action or workflow to a different anchor.",
    }


@mcp.tool()
async def validate_modifications(use_case_id: str, drop_steps: list[str] | None = None,
        answers: dict[str, Any] | None = None, ctx: Context | None = None) -> dict:
    """
    Check a requested set of changes BEFORE promising anything to the client.

    Three classes of failure, all hard blocks rather than warnings:

    dependency  — a surviving step DEPENDS_ON one being dropped
    schema      — a reconcile rule reads a schema nothing surviving produces.
                    This is the dangerous one: the join returns no rows, which
                    reads as "nobody is non-compliant" — a wrong answer that
                    looks like good news
    inputs      — a blocking input still unanswered
    unknown     — no such step in this use case

    There is no "this step is required" class. Nothing is authored as optional;
    legality comes entirely from the three structural checks above. If dropping a
    step breaks nothing and orphans no schema, it is legal.

    Call this before any sentence that commits to a change.
    """
    drop = list(drop_steps or [])
    ans = dict(answers or {})
    head = await q("""
        MATCH (u:UseCase {id:$id, isLatest:true})
        RETURN u.blockingInputs AS blocking
    """, ctx=ctx, id=use_case_id)
    if not head:
        return {"error": f"no use case {use_case_id!r}"}

    known = {r["id"] for r in await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        RETURN s.id AS id
    """, ctx=ctx, id=use_case_id)}

    problems: list[dict] = []
    for s in drop:
        if s not in known:
            problems.append({"class": "unknown", "step": s, "detail": f"no step {s!r} in this use case"})

    # Dropping everything satisfies every structural check vacuously and yields a
    # use case that answers nothing, so it is refused outright.
    if known and not (known - set(drop)):
        problems.append({"class": "empty", "step": None, "detail": "that drops every step — the clone would do nothing"})

    for r in await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(keep:UseCaseStep)
        WHERE NOT keep.id IN $drop
        MATCH (keep)-[:DEPENDS_ON]->(dep:UseCaseStep)
        WHERE dep.id IN $drop
        RETURN keep.id AS breaks, dep.id AS because
    """, ctx=ctx, id=use_case_id, drop=drop):
        problems.append({"class": "dependency", "step": r["breaks"],
                        "detail": f"{r['breaks']} depends on {r['because']}, "f"which you asked to drop"})

    for r in await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(reader:UseCaseStep)
        WHERE NOT reader.id IN $drop
        MATCH (reader)-[:READS_SCHEMA]->(es:EvidenceSchema)
        WHERE NOT EXISTS {
            MATCH (keep:UseCaseStep)-[:REFERENCES]->(es)
            WHERE NOT keep.id IN $drop
        }
        RETURN reader.id AS breaks, es.id AS schema
    """, ctx=ctx, id=use_case_id, drop=drop):
        problems.append({
            "class": "schema", "step": r["breaks"],
            "detail": f"{r['breaks']} reads {r['schema']}, which nothing surviving "
                    f"produces. The join would return no rows, which reads as "
                    f"'nobody is non-compliant'.",
        })

    missing = [k for k in (head[0]["blocking"] or []) if k not in ans or ans[k] in (None, "")]
    for k in missing:
        problems.append({"class": "inputs", "step": None, "detail": f"blocking input {k!r} not answered"})

    return {
        "useCaseId": use_case_id, "dropSteps": drop,
        "legal": not problems,
        "problems": problems,
        "verdict": "OK — safe to plan" if not problems
                else f"BLOCKED — {len(problems)} problem(s). Explain each to the "
                        f"client rather than proceeding.",
    }


@mcp.tool()
async def plan_clone(use_case_id: str, answers: dict[str, Any] | None = None,
        drop_steps: list[str] | None = None, ctx: Context | None = None) -> dict:
    """
    Render a clone plan. This NEVER executes anything.

    Publishing writes assessments, rule bindings and credential references into a
    live tenant, and reversing a bad publish is not cheap — so the plan is shown
    to the client for confirmation, and the publish itself is performed by the
    tenant's ComplianceCow instance, not by this server.

    `refsToResolve` lists every catalog reference the publish must resolve
    against PolicyCow or MinIO. An unresolvable ref must fail the publish rather
    than produce a half-built assessment.
    """
    check = await validate_modifications(use_case_id, drop_steps, answers, ctx=ctx)
    if check.get("error"):
        return check
    if not check["legal"]:
        return {"planned": False, "reason": "validation failed", **check}

    drop = list(drop_steps or [])
    steps = await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        WHERE NOT s.id IN $drop
        RETURN s.seq AS seq, s.id AS id, s.type AS type, s.level AS level,
            s.name AS name
        ORDER BY s.seq
    """, ctx=ctx, id=use_case_id, drop=drop)
    refs = await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        WHERE NOT s.id IN $drop
        MATCH (s)-[r]->(t) WHERE t.catalogRef IS NOT NULL
        RETURN DISTINCT labels(t)[0] AS kind, t.catalogRef AS ref
        ORDER BY kind, ref
    """, ctx=ctx, id=use_case_id, drop=drop)
    # The applications a create_application/create_control step binds. This is the part of the
    # plan that can fail for a reason outside the playbook — no credentials — and
    # it is not answerable from this database, so it is listed, not checked.
    #
    # Read off the step property rather than the REQUIRES_APPLICATION edge: a
    # templated application has no edge because there is no ref until an input is
    # answered, and a list that quietly omits one is worse than no list.
    apps = await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        WHERE NOT s.id IN $drop AND s.requiresApplication IS NOT NULL
        RETURN s.id AS step, s.requiresApplication AS application
        ORDER BY step
    """, ctx=ctx, id=use_case_id, drop=drop)
    for a in apps:
        if m := re.fullmatch(r"\$\{\{\s*inputs\.(\w+)\s*\}\}", a["application"]):
            a["fromInput"] = m.group(1)
            a["application"] = (answers or {}).get(m.group(1)) or None
            a["resolved"] = a["application"] is not None
    # Record-level steps fire once per matching row and nothing in the model
    # bounds that, so the count is not knowable from here. Surface them anyway:
    # they are the part of a plan whose blast radius depends on the tenant's data.
    fanout = await q("""
        MATCH (:UseCase {id:$id, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        WHERE NOT s.id IN $drop AND s.anchorLevel = 'record'
        RETURN s.id AS step, s.type AS type
    """, ctx=ctx, id=use_case_id, drop=drop)

    return {
        "planned": True, "executed": False,
        "useCaseId": use_case_id,
        "stepsToCreate": steps, "stepsDropped": drop,
        "applicationsRequired": apps,
        "refsToResolve": refs,
        "recordLevelSteps": fanout,
        "answers": answers or {},
        "confirmationRequired": True,
        "note": "Show this plan to the client and get an explicit yes before "
                "anything is published. Each step in recordLevelSteps fires once "
                "per matching row and nothing bounds that count, so say so plainly "
                "and dry-run against a completed run before enabling — the row "
                "count comes from the tenant's data, not from this plan. A use "
                "case does not declare assessment creation: publish resolves the "
                "Assessment a ControlConfig hangs off, so it is not shown here.",
    }


@mcp.tool()
async def record_gap(utterance: str, resolution: str = "no_match",
        nearest_use_case: str | None = None,
        missing: list[str] | None = None,
        ctx: Context | None = None) -> dict:
    """
    Persist a request the catalog could not serve.

    Call this on every NONE and every PARTIAL, not only outright misses. These
    records are the catalog roadmap — and they only exist if capture happens at
    the time, because the transcripts are gone later.

    resolution: no_match | partial | authored
    """
    if resolution not in ("no_match", "partial", "authored"):
        return {"error": "resolution must be no_match, partial or authored"}
    rid = f"req-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
    await w("""
        MERGE (r:UseCaseRequest {id:$rid})
        SET r.rawText = $text, r.resolution = $res,
            r.capturedAt = datetime(), r.missing = $missing
    """, ctx=ctx, rid=rid, text=utterance, res=resolution, missing=missing or [])
    if nearest_use_case:
        await w("""
            MATCH (r:UseCaseRequest {id:$rid})
            MATCH (u:UseCase {id:$uc, isLatest:true})
            MERGE (r)-[m:PARTIALLY_MATCHED]->(u)
            SET m.missingCapabilities = $missing
        """, ctx=ctx, rid=rid, uc=nearest_use_case, missing=missing or [])
    return {"recorded": rid, "resolution": resolution,
            "nearestUseCase": nearest_use_case}


@mcp.tool()
async def open_gaps(limit: int = 20, ctx: Context | None = None) -> list[dict]:
    """
    Requests the catalog could not serve, most-asked first. This is the roadmap
    input: what clients keep asking for that does not exist yet.
    """
    return await q("""
        MATCH (r:UseCaseRequest)
        WHERE r.resolution IN ['no_match','partial']
        OPTIONAL MATCH (r)-[m:PARTIALLY_MATCHED]->(u:UseCase)
        RETURN r.rawText AS request, r.resolution AS resolution,
            toString(r.capturedAt) AS capturedAt,
            u.name AS nearest, m.missingCapabilities AS missing
        ORDER BY r.capturedAt DESC LIMIT $limit
    """, ctx=ctx, limit=limit)
