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


async def _control_lineage_rows(use_case_id: str, step_id: str | None = None,
        ctx: Context | None = None) -> list[dict]:
    """
    Walk the control lineage from source to target using the stored
    :ROLLS_UP_FROM edges. The graph direction is target -> source, so we
    reverse the path to return a source-first ordering.
    """
    rows = await q("""
        MATCH (:UseCase {id:$uc, isLatest:true})-[:HAS_STEP]->(target:UseCaseStep)
        WHERE ($stepId IS NULL OR target.id = $stepId)
        OPTIONAL MATCH path = (source:UseCaseStep)<-[:ROLLS_UP_FROM*1..]-(target)
        WITH target, collect(path) AS paths
        UNWIND paths AS p
        WITH target, p,
             [n IN nodes(p) | {
                id: n.id,
                type: n.type,
                level: n.level,
                name: n.name
             }] AS chain,
             [n IN nodes(p) | n.id] AS chainIds,
             length(p) AS depth
        RETURN target.id AS targetStep,
               target.name AS targetName,
               chain,
               chainIds,
               depth
        ORDER BY depth ASC, targetStep
    """, ctx=ctx, uc=use_case_id, stepId=step_id)
    return rows


async def _step_control_details(use_case_id: str, step_ids: list[str],
        ctx: Context | None = None) -> dict[str, dict]:
    """Fetch user-facing control details for a set of steps."""
    if not step_ids:
        return {}
    rows = await q("""
        MATCH (:UseCase {id:$uc, isLatest:true})-[:HAS_STEP]->(s:UseCaseStep)
        WHERE s.id IN $stepIds
        OPTIONAL MATCH (s)-[:IN_ASSESSMENT]->(assessment:Assessment)
        OPTIONAL MATCH (s)-[:EXECUTES]->(rule:Rule)
        OPTIONAL MATCH (s)-[:USES_RULE]->(ruleList:Rule)
        OPTIONAL MATCH (s)-[:REFERENCES]->(evidence:EvidenceSchema)
        OPTIONAL MATCH (s)-[:CONFIGURES]->(cfg:ControlConfig)
        RETURN s.id AS id,
               s.type AS type,
               s.level AS level,
               s.name AS name,
               s.description AS description,
               s.config AS config,
               collect(DISTINCT assessment.name) AS assessmentNames,
               collect(DISTINCT assessment.ref) AS assessmentRefs,
               collect(DISTINCT rule.name) AS ruleNames,
               collect(DISTINCT rule.ref) AS ruleRefs,
               collect(DISTINCT ruleList.name) AS ruleListNames,
               collect(DISTINCT ruleList.ref) AS ruleListRefs,
               collect(DISTINCT evidence.name) AS evidenceNames,
               collect(DISTINCT evidence.ref) AS evidenceRefs,
               collect(DISTINCT cfg.ref) AS controlConfigRefs
        ORDER BY s.id
    """, ctx=ctx, uc=use_case_id, stepIds=step_ids)

    details: dict[str, dict] = {}
    for r in rows:
        cfg = r["config"] or {}
        assessment_names = [x for x in (r["assessmentNames"] or []) if x]
        assessment_refs = [x for x in (r["assessmentRefs"] or []) if x]
        rule_names = [x for x in ((r["ruleNames"] or []) + (r["ruleListNames"] or [])) if x]
        rule_refs = [x for x in ((r["ruleRefs"] or []) + (r["ruleListRefs"] or [])) if x]
        evidence_names = [x for x in (r["evidenceNames"] or []) if x]
        evidence_refs = [x for x in (r["evidenceRefs"] or []) if x]
        displayable = (cfg or {}).get("displayable") or (cfg or {}).get("alias")
        details[r["id"]] = {
            "id": r["id"],
            "type": r["type"],
            "level": r["level"],
            "name": r["name"],
            "description": r["description"],
            "displayable": displayable,
            "assessment": assessment_names[0] if assessment_names else (
                assessment_refs[0] if assessment_refs else "Not configured"
            ),
            "assessmentRefs": assessment_refs,
            "ruleNames": rule_names,
            "ruleRefs": rule_refs,
            "evidenceNames": evidence_names,
            "evidenceRefs": evidence_refs,
            "controlConfigRefs": r["controlConfigRefs"] or [],
            "config": cfg,
        }
    return details


async def get_control_lineage(use_case_id: str, step_id: str | None = None,
        ctx: Context | None = None) -> dict:
    """
    Return linked control lineage in a source-first ordering: lowest source step
    first, then intermediate steps, ending with the target control.

    This is intentionally additive and does not change the existing match logic.
    """
    rows = await _control_lineage_rows(use_case_id, step_id, ctx=ctx)
    seen: set[str] = set()
    ordered: list[dict] = []
    for r in rows:
        for node in r["chain"] or []:
            node_id = node["id"]
            if node_id in seen:
                continue
            seen.add(node_id)
            ordered.append({
                **node,
                "order": len(ordered) + 1,
                "position": "source" if len(ordered) == 0 else (
                    "target" if node_id == step_id else "intermediate"
                ),
            })

    direct = await q("""
        MATCH (:UseCase {id:$uc, isLatest:true})-[:HAS_STEP]->(target:UseCaseStep)
        WHERE ($stepId IS NULL OR target.id = $stepId)
        OPTIONAL MATCH (target)-[r:ROLLS_UP_FROM]->(source:UseCaseStep)
        RETURN target.id AS targetStep,
               collect({
                   id: source.id,
                   type: source.type,
                   level: source.level,
                   name: source.name,
                   description: source.description,
                   displayable: source.config.displayable,
                   assessment: source.refs.assessment,
                   linkType: r.linkType,
                   propagation: r.propagation,
                   linkedBy: r.linkedBy
               }) AS directSources
        ORDER BY targetStep
    """, ctx=ctx, uc=use_case_id, stepId=step_id)

    mapped = {row["targetStep"]: row["directSources"] or [] for row in direct}
    target = step_id if step_id else None
    source_steps = [n for n in ordered if n.get("position") == "source"]
    target_steps = [n for n in ordered if n.get("position") == "target"]
    source_ids = [n["id"] for n in source_steps]
    target_ids = [n["id"] for n in target_steps]
    step_ids = list(dict.fromkeys(source_ids + target_ids))
    step_details = await _step_control_details(use_case_id, step_ids, ctx=ctx)

    source_details = []
    for item in source_steps:
        detail = step_details.get(item["id"], {})
        source_details.append({
            "id": item["id"],
            "name": detail.get("name") or item.get("name"),
            "description": detail.get("description"),
            "displayable": detail.get("displayable"),
            "assessment": detail.get("assessment"),
            "level": detail.get("level") or item.get("level"),
            "type": detail.get("type") or item.get("type"),
            "ruleNames": detail.get("ruleNames", []),
            "evidenceNames": detail.get("evidenceNames", []),
            "linkedTo": target_ids[0] if target_ids else None,
            "linkType": "control",
        })

    target_details = []
    for item in target_steps:
        detail = step_details.get(item["id"], {})
        target_details.append({
            "id": item["id"],
            "name": detail.get("name") or item.get("name"),
            "description": detail.get("description"),
            "displayable": detail.get("displayable"),
            "assessment": detail.get("assessment"),
            "level": detail.get("level") or item.get("level"),
            "type": detail.get("type") or item.get("type"),
            "ruleNames": detail.get("ruleNames", []),
            "evidenceNames": detail.get("evidenceNames", []),
            "linkedFrom": source_ids[0] if source_ids else None,
            "linkType": "control",
        })

    chain_text = " -> ".join(
        [f"{n['id']} ({n['name'] or n['type']})" for n in ordered] or ["no linked controls"]
    )
    return {
        "useCaseId": use_case_id,
        "targetStep": target,
        "orderedChain": ordered,
        "sourceControls": source_steps,
        "targetControls": target_steps,
        "sourceControlDetails": source_details,
        "targetControlDetails": target_details,
        "lineageByTarget": mapped,
        "hasLineage": bool(ordered),
        "summaryText": (
            f"Linked control chain: {chain_text}. "
            f"Source controls appear first, and the final target control is last."
            if ordered else "No linked control lineage found for the requested step."
        ),
    }


# ── tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def catalog_stats(ctx: Context | None = None) -> dict:
    """
    Purpose:
        Return the current Playbook catalog size, shape, and matcher mode.

    When to call:
        Use this as a connectivity check or a quick health/status probe before
        matching against the catalog.

    Inputs:
        None.

    Output contract:
        Returns use-case count, step count, domains, open gaps, matcher mode,
        and the fetch database endpoint.

    Rules:
        Keep this call simple and read-only. Do not substitute it for a requirement
        match when the agent is trying to determine capability coverage.
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
    Purpose:
        Browse the catalog and list the latest version of each use case.

    When to call:
        Use this when the caller asks what use cases exist, not when they describe
        a required capability or a specific problem to solve.

    Inputs:
        domain: optional domain filter.
        lifecycle: published | draft | deprecated or null for all.

    Output contract:
        Returns a list of use cases with id, version, name, domain, levels, and
        step count.

    Rules:
        Do not use this as a substitute for the requirement-driven match tools.
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
    Purpose:
        Match a user's requirement to the best Playbook use-case candidates.

    When to call:
        This is the mandatory first step for any requirement-driven request. Call
        it before any workflow, capability, or assessment tool when the user is
        describing what they need.

    Inputs:
        utterance: the user requirement in natural language.
        limit: maximum number of candidate use cases to return.

    Output contract:
        Returns the utterance, matcher mode, candidate list, thresholds, guidance,
        and the best-match classification.

    Rules:
        - Match actual intent and required outcome, not keywords alone.
        - Treat outOfScope as authoritative catalog information.
        - Do not claim FULL from a similar name or description alone.
        - Consider blockingInputs and use-case coverage.
        - For control-heavy scenarios, a matched use case may expose linked
          controls through ROLLS_UP_FROM; the source controls should appear before
          the target control in the chain.
        - Do not invent capabilities, integrations, inputs, outputs, or steps.

    Result classes:
        FULL: the use case satisfies the requirement.
        PARTIAL: useful coverage exists but the requirement is not fully met.
        NONE: no suitable use case exists, so record a gap.

    Flow:
        match_use_case -> FULL => continue with the matched use case
        match_use_case -> PARTIAL => match_steps -> record_gap
        match_use_case -> NONE => record_gap
    """
    rows = await q("""
        MATCH (u:UseCase {isLatest:true})
        OPTIONAL MATCH (u)-[:HAS_STEP]->(s:UseCaseStep)
        RETURN u.id AS id, u.version AS version, u.name AS name,
            u.description AS description,
            u.inScope AS inScope, u.outOfScope AS outOfScope,
            u.blockingInputs AS blockingInputs, u.levels AS levels,
            s.detail AS detail,
            s.config AS config,
            s.requiresApplication AS requiresApplication,
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
    Purpose:
        Match reusable steps rather than full use cases.

    When to call:
        Use this after a PARTIAL match or when a requirement is best satisfied by
        composing multiple reusable building blocks.

    Inputs:
        utterance: the requirement or gap to cover.
        limit: maximum number of matching steps to return.
        exclude_use_case: optional use case to exclude from the search.
        use_case_ids: optional use-case subset to search within.

    Output contract:
        Returns candidate steps with their metadata and an `adaptedFrom` path.

    Rules:
        - Prefer the FULL and PARTIAL candidates from match_use_case to narrow the
          step search.
        - A step is not a complete solution; it is a reusable building block.
        - Preserve the source chain when a matching step belongs to a linked
          control lineage by checking the control lineage metadata and source
          relationships.
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
    Purpose:
        Return the full use case in client-facing terms, including steps, links,
        dependencies, and config.

    When to call:
        Use this after a FULL or PARTIAL match to explain the candidate in a human-
        readable way.

    Inputs:
        use_case_id: the use case to describe.

    Output contract:
        Returns the use case metadata and all declared steps with structured
        dependencies and configuration.

    Rules:
        - Explain steps in plain language.
        - Keep raw Neo4j internals only when they matter for the explanation.
        - If a field is absent, say it is not defined rather than guessing.
        - For control-heavy use cases, include any relevant upstream linkage as part
          of the explanation, ordered from source to target.
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
        RETURN
            s.seq AS seq,
            s.id AS id,
            s.type AS type,
            s.level AS level,
            s.name AS name,
            s.description AS description,
            s.inScope AS inScope,
            s.outOfScope AS outOfScope,
            s.mustAnswer AS mustAnswer,
            s.detail AS detail,
            s.config AS config,
            s.requiresApplication AS requiresApplication,
            collect(DISTINCT d.id) AS dependsOn
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
    Purpose:
        Explain one step: what it touches, what it depends on, and what depends on it.

    When to call:
        Use this when the caller asks why a step exists, before proposing to drop a
        step, or when the control lineage for one step needs to be explained.

    Inputs:
        use_case_id: the owning use case.
        step_id: the step to explain.

    Output contract:
        Returns the step metadata, direct dependencies, dependent steps, touched
        objects, and the source-to-target control lineage when relevant.

    Rules:
        - Keep the explanation step-centric.
        - Always include dependency context and upstream control lineage if present.
        - Source controls should appear before the target control in the returned chain.
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
    lineage = await get_control_lineage(use_case_id, step_id, ctx=ctx)
    return {**head[0], **deps, "touches": touches,
            "controlLineage": lineage["orderedChain"],
            "sourceControls": lineage["sourceControls"],
            "targetControls": lineage["targetControls"],
            "sourceControlDetails": lineage["sourceControlDetails"],
            "targetControlDetails": lineage["targetControlDetails"],
            "directControlSources": lineage["lineageByTarget"].get(step_id, []),
            "controlLineageSummary": lineage["summaryText"]}


@mcp.tool()
async def get_control_lineage_summary(use_case_id: str, step_id: str | None = None,
        ctx: Context | None = None) -> dict:
    """
    Purpose:
        Return the full upstream control lineage for a use case or a specific step.

    When to call:
        Use this when the requirement is based on source-to-target control mapping,
        such as source controls linked to target controls in a control lineage.

    Inputs:
        use_case_id: the use case to inspect.
        step_id: optional target step to inspect; omit to inspect the full use case.

    Output contract:
        Returns the ordered chain, source controls, target controls, and a summary
        string with the source-first order preserved.

    Rules:
        - Keep the final chain ordered from source to target.
        - The target control should be the last element in the chain.
        - This is additive and should not replace the standard match logic.
    """
    data = await get_control_lineage(use_case_id, step_id, ctx=ctx)
    return {
        "useCaseId": data["useCaseId"],
        "targetStep": data["targetStep"],
        "orderedChain": data["orderedChain"],
        "sourceControls": data["sourceControls"],
        "targetControls": data["targetControls"],
        "sourceControlDetails": data["sourceControlDetails"],
        "targetControlDetails": data["targetControlDetails"],
        "summaryText": data["summaryText"],
        "hasLineage": data["hasLineage"],
    }


@mcp.tool()
async def get_modification_surface(use_case_id: str, ctx: Context | None = None) -> dict:
    """
    Purpose:
        Return the editable surface of a use case: what can change, and which
        inputs must be answered first.

    When to call:
        Use this before offering a plan or describing what a client may change.

    Inputs:
        use_case_id: the use case whose modification surface is needed.

    Output contract:
        Returns the blocking inputs, full input schema, and step-level config.

    Rules:
        - `blockingInputs` must be answered before any plan exists.
        - A literal value is not negotiable without authoring work.
        - A step is not optional merely because it looks small; legality is based on
          structure and validation, not author intent.
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
    Purpose:
        Validate a proposed set of changes before any plan is offered.

    When to call:
        Call this before committing to a change, especially before dropping steps
        or answering a client request with a plan.

    Inputs:
        use_case_id: the use case being modified.
        drop_steps: step ids the client wants removed.
        answers: any blocking inputs already answered.

    Output contract:
        Returns whether the change set is legal and enumerates any hard-block
        problems.

    Rules:
        - Hard blocks are dependency, schema, input, and unknown-step issues.
        - Nothing is authored as optional; legality comes from structure, not
          author guesswork.
        - If the set is legal, the planner can continue; if not, explain the issue
          instead of proceeding.
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
