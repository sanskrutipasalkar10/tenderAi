"""Reduce pass — the three per-document judgment modules (go_no_go, synopsis,
risk_finder) that run once all of a document's chunks have been map-passed
(docs/SPEC.md §2.1 stage 4). Routed through app.llm.structured, never a provider SDK
directly (CLAUDE.md hard rule 1). Prompts are versioned files (hard rule 2).

Decision/score/severity math is deliberately code, not prompt instructions (hard rule
3): the model is asked only for the genuinely interpretive part of each module (does
this company value satisfy this criterion; what severity tier does this clause fall
in; how should this document be summarized) and reduce_pass.py computes the rest —
see docs/DECISIONS.md #38-40 for why each of these specific splits was chosen.
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import DataQualityError
from app.core.logging import get_logger
from app.guardrails.output_checks import validate_analysis_result
from app.llm.structured import complete_structured
from app.models.chunk import Chunk
from app.models.chunk_extraction import ChunkExtraction
from app.models.document import Document
from app.models.document_analysis import DocumentAnalysis
from app.models.schemas import (
    GoNoGoCriterionMatch,
    GoNoGoDecision,
    GoNoGoHumanOverride,
    GoNoGoLLMResult,
    GoNoGoResult,
    GoNoGoStatus,
    MapPassAmountFact,
    MapPassCriterionFact,
    MapPassDateFact,
    MapPassResult,
    RiskFinderLLMResult,
    RiskFinderResult,
    SynopsisLLMResult,
    SynopsisResult,
)
from app.pipeline.citation_verify import verify_risk_citations
from app.prompts.registry import load_prompt

logger = get_logger(__name__)

# Company-profile fields required to run a real (non-Conditional-Go) eligibility check.
# Derived from evals/datasets/golden_adversarial.jsonl's incomplete_company_profile
# case: profile_incomplete has certifications=null and sectors=null (both flagged as
# gaps) while past_projects=[] and a 1-item geographic_presence are NOT flagged — so
# "required" here means "must not be null," not "must be non-empty." See
# docs/DECISIONS.md #38.
REQUIRED_PROFILE_FIELDS = (
    "company_name",
    "annual_turnover",
    "certifications",
    "sectors",
    "max_capacity_pct",
)

# Code-based severity rubric (CLAUDE.md hard rule 3 + the plan's own open decision:
# "risk severity thresholds... encode as an explicit rubric, not model discretion").
# Derived from evals/datasets/golden_risk_finder.jsonl, where every fixture's
# category->severity mapping is 100% consistent — this is a real, evidence-grounded
# starting rubric, not a guess. See docs/DECISIONS.md #39.
SEVERITY_BY_CATEGORY: dict[str, str] = {
    "Liquidated Damages": "HIGH",
    "Indemnity": "HIGH",
    "Payment Terms": "MEDIUM",
    "Termination": "MEDIUM",
    "Force Majeure": "LOW",
}
# Unrecognized category -> safe middle default, logged below. Confirmed a real, common
# case in practice, not just a theoretical fallback: a live validation run against a
# real tender found 11 of its 11 real risk categories (EMD Forfeiture, Security
# Deposit Recovery, Right to Reverse Auction, etc.) fell outside the 5-category rubric
# above, which was derived only from the small golden fixture set (docs/DECISIONS.md
# #39) — the rubric needs real domain-expert review/expansion before this defaults to
# anything more consequential than MEDIUM.
DEFAULT_SEVERITY = "MEDIUM"

# risk_score formula (docs/DECISIONS.md #39): a simple weighted count, capped at 100.
_SEVERITY_WEIGHT = {"HIGH": 30, "MEDIUM": 15, "LOW": 5}

# --- go_no_go: hard-fail gates + weighted score (Phase 1 of
# docs/pq-tq-framework-implementation-plan.md — see docs/DECISIONS.md for the full
# row, including why these are Python constants rather than DB reference tables in
# this phase). Verbatim gate names from that plan's Section 3. ------------------------
HARD_FAIL_GATES = (
    "Mandatory PQ experience unavailable",
    "Turnover not met and no valid exemption",
    "Mandatory certification unavailable",
    "Mandatory OEM authorization unavailable",
    "Mandatory manpower unavailable",
    "Required consortium/partner route unavailable",
    "Unacceptable legal/commercial terms",
)

# The 8-factor Bid/No-Bid weighted score (docs/pq-tq-framework-implementation-plan.md
# §4, matching Table 26 of docs/sutf-company-profile-decision-grade.docx exactly —
# sums to 100).
BID_DECISION_FACTOR_WEIGHTS: dict[str, int] = {
    "PQ Eligibility": 30,
    "Similar Experience": 20,
    "Technical Capability": 15,
    "Government/PSU Experience": 10,
    "Key Manpower": 10,
    "Financial Capability": 5,
    "Strategic Relevance": 5,
    "Partner/OEM Availability": 5,
}


def _effective_status(match: GoNoGoCriterionMatch) -> GoNoGoStatus:
    """A human override (app.api.routes_analysis's review endpoint) always wins over
    the model's original status — that's the entire point of reviewing a criterion.
    """
    return match.human_override.status if match.human_override else match.status


def check_hard_gates(criteria_matches: list[GoNoGoCriterionMatch]) -> list[str]:
    """Deterministic pre-check (CLAUDE.md hard rule 3 / docs/SPEC.md §10 — this is a
    pipeline, not an agent, so control-flow decisions are code, not prompt
    instructions). A criterion match only triggers a gate if the model itself tagged
    it (`gate` field, set only on a non-"pass" status) — the model does the
    interpretive work of connecting a specific failed criterion to a named gate; this
    function just enforces the resulting control flow.

    Only "eligibility"-type criteria are ever considered — enforced here, not only by
    the prompt's instruction that a "procedural" criterion should never carry a gate
    (defense in depth, hard rule 3). "insufficient_data" triggers exactly like "fail"
    (no evidence is never treated as a free pass by default, per the source
    framework's own "do not mark qualified without documentary evidence" stance) —
    until a human_override resolves it, which _effective_status applies first.

    Returns the triggered gate names in HARD_FAIL_GATES' own order (empty = no hard
    fail).
    """
    triggered = {
        m.gate
        for m in criteria_matches
        if m.criterion_type == "eligibility"
        and _effective_status(m) != "pass"
        and m.gate is not None
    }
    return [gate for gate in HARD_FAIL_GATES if gate in triggered]


def compute_weighted_score(factor_scores: dict[str, int]) -> float:
    """Weighted sum over BID_DECISION_FACTOR_WEIGHTS. Raises if the model omitted a
    factor — a real validation failure that should surface loudly (as a ProviderError
    the caller's normal retry/fallback handles), not silently default to 0 and mask a
    prompt-compliance problem.
    """
    missing = set(BID_DECISION_FACTOR_WEIGHTS) - set(factor_scores)
    if missing:
        raise ValueError(f"factor_scores is missing required factors: {sorted(missing)}")
    return sum(
        factor_scores[factor] * weight / 100
        for factor, weight in BID_DECISION_FACTOR_WEIGHTS.items()
    )


def decide(score: float) -> GoNoGoDecision:
    """Score bands, verbatim from docs/pq-tq-framework-implementation-plan.md §4."""
    if score >= 80:
        return "Go"
    if score >= 65:
        return "Go (Management Review)"
    if score >= 50:
        return "Conditional-Go (Partner Required)"
    return "No-Go"


def apply_human_overrides(
    result: dict[str, Any],
    overrides: list[tuple[int, Literal["pass", "fail"], str | None]],
) -> dict[str, Any]:
    """Applies a bid-team member's review of specific eligibility criteria to an
    already-computed go_no_go `result` dict, then recomputes `decision`/`gaps`/`score`
    from the effective (overridden) statuses via the same check_hard_gates/decide this
    module always uses — never a second LLM call, never re-asking the model for a
    decision (hard rule 3 still applies to human-reviewed results, not just model ones).

    Deliberate scope boundary: this changes gate-triggering and therefore `decision`,
    but never touches `factor_scores` — those stay the model's original holistic
    judgment. Reviewing one criterion doesn't retroactively re-score the other 7
    factors; that would need a second LLM call this function is designed to avoid.

    Raises DataQualityError for an out-of-range `criterion_index` or an attempt to
    review a "procedural" criterion (procedural criteria never feed check_hard_gates,
    so there's nothing for a human override to change — see docs/DECISIONS.md).
    """
    criteria_matches = list(result.get("criteria_matches", []))
    now = datetime.now(timezone.utc)

    for criterion_index, status, note in overrides:
        if not 0 <= criterion_index < len(criteria_matches):
            raise DataQualityError(
                f"criterion_index {criterion_index} is out of range "
                f"(this analysis has {len(criteria_matches)} criteria_matches)"
            )
        match = GoNoGoCriterionMatch.model_validate(criteria_matches[criterion_index])
        if match.criterion_type != "eligibility":
            raise DataQualityError(
                f"criterion_index {criterion_index} ('{match.criterion}') is "
                "'procedural', not 'eligibility' — procedural criteria don't feed "
                "scoring, so there's nothing to review"
            )
        match.human_override = GoNoGoHumanOverride(
            status=status, note=note, original_status=match.status, reviewed_at=now
        )
        criteria_matches[criterion_index] = match.model_dump(mode="json")

    matches_models = [GoNoGoCriterionMatch.model_validate(m) for m in criteria_matches]
    triggered_gates = check_hard_gates(matches_models)

    factor_scores = result.get("factor_scores")
    if factor_scores is not None:
        weighted_score = compute_weighted_score(factor_scores)
        decision: GoNoGoDecision = "No-Go" if triggered_gates else decide(weighted_score)
        score = round(weighted_score)
    else:
        # The pre-LLM short-circuit paths (missing profile fields / no criteria found)
        # never computed a weighted score to begin with — an override here can only
        # ever confirm the existing decision, never manufacture a score that was never
        # computed.
        decision = result["decision"]
        score = result["score"]

    return {**result, "criteria_matches": criteria_matches, "gaps": triggered_gates,
            "decision": decision, "score": score}


def _aggregate_chunk_facts(db: Session, document: Document) -> MapPassResult:
    """Merges every chunk's MapPassResult for this document into one. Chunks overlap
    by design (docs/DECISIONS.md #35), so near-duplicate facts from adjacent chunks are
    expected here — deduped downstream where it matters (dates/amounts for synopsis),
    left to the reduce-pass model to merge where it matters (risk_candidates).
    """
    chunk_ids = [c.id for c in db.query(Chunk).filter(Chunk.document_id == document.id).all()]
    extractions = (
        db.query(ChunkExtraction).filter(ChunkExtraction.chunk_id.in_(chunk_ids)).all()
        if chunk_ids
        else []
    )

    aggregated = MapPassResult()
    for extraction in extractions:
        result = MapPassResult.model_validate(extraction.structured_json)
        aggregated.dates.extend(result.dates)
        aggregated.amounts.extend(result.amounts)
        aggregated.criteria.extend(result.criteria)
        aggregated.risk_candidates.extend(result.risk_candidates)
    return aggregated


def _dedupe_facts(facts: Sequence[MapPassDateFact | MapPassAmountFact]) -> list[dict]:
    """Collapses same (label, value) facts to their first page_ref — real tenders
    routinely restate the same date/amount on every page (a header/footer stamp, or a
    cover page repeated in a corrigendum), and chunk overlap (docs/DECISIONS.md #35)
    multiplies that further; a real 6-page BHEL fixture produced the same "Tender
    Dated: 17-06-2019" fact 6 times, once per page, before this fix. Keeping only the
    first page_ref is still a fully real, verifiable citation (hard rule 7's zero
    hallucination tolerance is unaffected — nothing is invented, just not repeated) —
    only fuzzy near-duplicate MERGING (different wording, same fact) stays the reduce
    model's job for risk_candidates, not attempted here for dates/amounts.
    """
    seen: dict[tuple[str, str], dict] = {}
    for fact in facts:
        key = (fact.label, fact.value)
        if key not in seen:
            seen[key] = fact.model_dump()
    return list(seen.values())


def _upsert_analysis(
    db: Session, document_id: UUID, module: str, result: dict[str, Any], model_used: str | None
) -> DocumentAnalysis:
    """UNIQUE(document_id, module) means this is always an upsert, never a duplicate
    insert — re-running a module on an already-analyzed document replaces its result
    rather than erroring or accumulating stale rows.
    """
    existing = (
        db.query(DocumentAnalysis)
        .filter(DocumentAnalysis.document_id == document_id, DocumentAnalysis.module == module)
        .first()
    )
    if existing is not None:
        existing.result = result
        existing.model_used = model_used
        db.commit()
        db.refresh(existing)
        return existing

    analysis = DocumentAnalysis(
        document_id=document_id, module=module, result=result, model_used=model_used
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


# --- go_no_go ----------------------------------------------------------------------


def _missing_profile_fields(company_profile: dict) -> list[str]:
    return [f for f in REQUIRED_PROFILE_FIELDS if company_profile.get(f) is None]


# Short-circuit paths (missing profile data / no criteria to check) don't have a
# weighted score to band, so they reuse the closest of the 4 real decision values —
# "Conditional-Go (Partner Required)" is the nearest match to the old plain
# "Conditional-Go" in spirit ("not a clean yes/no, something needed before
# proceeding"), even though the parenthetical is about a partner/OEM gap specifically
# in the framework's own usage. Not a new 5th value — the schema only allows the 4.
_INSUFFICIENT_DATA_DECISION: GoNoGoDecision = "Conditional-Go (Partner Required)"


def run_go_no_go(db: Session, document: Document, company_profile: dict) -> DocumentAnalysis:
    """Compares `company_profile` against every eligibility criterion found in the
    document. Never guesses a Go/No-Go: an incomplete profile or a document with no
    extracted criteria both short-circuit without an LLM call (docs/SPEC.md §7's "I
    don't know" path). Otherwise runs the Phase 1 hard-gate + weighted-score formula
    (docs/pq-tq-framework-implementation-plan.md §3-4, docs/DECISIONS.md) — a real
    behavior change from the old "any criterion fails -> No-Go" rule: a failing
    criterion only forces No-Go if the model tagged it as one of the 7 named hard
    gates; otherwise it just pulls down the relevant factor score.
    """
    missing_fields = _missing_profile_fields(company_profile)
    facts = _aggregate_chunk_facts(db, document)

    if missing_fields:
        logger.info(
            "reduce_pass.go_no_go_incomplete_profile",
            document_id=str(document.id),
            missing_fields=missing_fields,
        )
        result = GoNoGoResult(
            score=0, decision=_INSUFFICIENT_DATA_DECISION, gaps=missing_fields
        )
        model_used = None
    elif not facts.criteria:
        logger.warning("reduce_pass.go_no_go_no_criteria_found", document_id=str(document.id))
        result = GoNoGoResult(
            score=0,
            decision=_INSUFFICIENT_DATA_DECISION,
            gaps=["No eligibility criteria found in document"],
        )
        model_used = None
    else:
        content = _format_criteria_content(facts.criteria)
        prompt = (
            load_prompt("reduce", "v1_go_no_go")
            .replace("{company_profile}", _format_company_profile(company_profile))
            .replace("{content}", content)
        )
        llm_result, model_used = complete_structured("reduce", prompt, GoNoGoLLMResult)

        triggered_gates = check_hard_gates(llm_result.criteria_matches)
        weighted_score = compute_weighted_score(llm_result.factor_scores)
        decision: GoNoGoDecision = "No-Go" if triggered_gates else decide(weighted_score)
        result = GoNoGoResult(
            score=round(weighted_score),
            decision=decision,
            criteria_matches=llm_result.criteria_matches,
            gaps=triggered_gates,
            next_steps=llm_result.next_steps,
            factor_scores=llm_result.factor_scores,
        )

    validated = validate_analysis_result("go_no_go", result.model_dump())
    return _upsert_analysis(db, document.id, "go_no_go", validated, model_used)


def _format_criteria_content(criteria: list[MapPassCriterionFact]) -> str:
    return "\n".join(f"[PAGE {c.page_ref}] {c.description}" for c in criteria)


def _format_company_profile(company_profile: dict) -> str:
    lines = [f"{key}: {value}" for key, value in company_profile.items()]
    return "\n".join(lines)


# --- risk_finder ---------------------------------------------------------------------


def run_risk_finder(db: Session, document: Document) -> DocumentAnalysis:
    """Consolidates every risk_candidate found across the document's chunks into a
    final, de-duplicated, severity-scored risk list.
    """
    facts = _aggregate_chunk_facts(db, document)

    if not facts.risk_candidates:
        logger.info("reduce_pass.risk_finder_no_candidates", document_id=str(document.id))
        result = RiskFinderResult(risk_score=0, risks=[])
        model_used = None
    else:
        content = _format_risk_candidates_content(facts.risk_candidates)
        prompt = load_prompt("reduce", "v1_risk_finder").replace("{content}", content)
        llm_result, model_used = complete_structured("reduce", prompt, RiskFinderLLMResult)

        risks_with_severity = [
            {
                "category": r.category,
                "clause_summary": r.clause_summary,
                "page_ref": r.page_ref,
                "severity": _severity_for_category(r.category),
            }
            for r in llm_result.risks
        ]
        risks_verified = verify_risk_citations(db, document.id, risks_with_severity)
        risk_score = min(100, sum(_SEVERITY_WEIGHT[r["severity"]] for r in risks_verified))
        result = RiskFinderResult.model_validate(
            {"risk_score": risk_score, "risks": risks_verified}
        )

    validated = validate_analysis_result("risk_finder", result.model_dump())
    return _upsert_analysis(db, document.id, "risk_finder", validated, model_used)


def _format_risk_candidates_content(candidates: list) -> str:
    return "\n".join(
        f"[PAGE {c.page_ref}] category={c.category}: {c.clause_summary}" for c in candidates
    )


def _severity_for_category(category: str) -> str:
    severity = SEVERITY_BY_CATEGORY.get(category)
    if severity is None:
        logger.warning(
            "reduce_pass.unrecognized_risk_category",
            category=category,
            default_severity=DEFAULT_SEVERITY,
        )
        return DEFAULT_SEVERITY
    return severity


# --- synopsis --------------------------------------------------------------------


def run_synopsis(db: Session, document: Document) -> DocumentAnalysis:
    """Writes the document synopsis. `key_dates`/`financials` are the already-verified,
    page-cited map-pass facts passed through directly (hard rule 7: zero hallucination
    tolerance for dates/amounts) — not re-generated by a second LLM call.
    """
    facts = _aggregate_chunk_facts(db, document)
    key_dates = _dedupe_facts(facts.dates)
    financials = _dedupe_facts(facts.amounts)

    if not facts.dates and not facts.amounts and not facts.criteria:
        logger.warning("reduce_pass.synopsis_no_facts_found", document_id=str(document.id))
        result = SynopsisResult(
            title="Unknown",
            issuing_authority="Unknown",
            key_dates=[],
            financials=[],
            scope_summary="Not enough extracted facts to summarize this document.",
            eligibility_summary="Not enough extracted facts to summarize this document.",
            payment_terms_summary="Not enough extracted facts to summarize this document.",
            confidence="low",
        )
        model_used = None
    else:
        content = _format_synopsis_content(facts)
        prompt = load_prompt("reduce", "v1_synopsis").replace("{content}", content)
        llm_result, model_used = complete_structured("reduce", prompt, SynopsisLLMResult)

        result = SynopsisResult.model_validate(
            {
                "title": llm_result.title,
                "issuing_authority": llm_result.issuing_authority,
                "key_dates": key_dates,
                "financials": financials,
                "scope_summary": llm_result.scope_summary,
                "eligibility_summary": llm_result.eligibility_summary,
                "payment_terms_summary": llm_result.payment_terms_summary,
                "confidence": llm_result.confidence,
            }
        )

    validated = validate_analysis_result("synopsis", result.model_dump())
    return _upsert_analysis(db, document.id, "synopsis", validated, model_used)


def _format_synopsis_content(facts: MapPassResult) -> str:
    lines = []
    for d in facts.dates:
        lines.append(f"[PAGE {d.page_ref}] date: {d.label} = {d.value}")
    for a in facts.amounts:
        lines.append(f"[PAGE {a.page_ref}] amount: {a.label} = {a.value}")
    for c in facts.criteria:
        lines.append(f"[PAGE {c.page_ref}] criterion: {c.description}")
    return "\n".join(lines)


def run_reduce_pass_for_document(
    db: Session, document: Document, company_profile: dict
) -> list[DocumentAnalysis]:
    """Runs all three modules for a document. Each module's failure (a ProviderError
    from complete_structured, after cloud+local fallback both fail) is independent —
    matches the map pass's per-unit-of-work isolation, here per-module instead of
    per-chunk (Phase 5's fan-in counterpart to Phase 4's fan-out).
    """
    return [
        run_go_no_go(db, document, company_profile),
        run_synopsis(db, document),
        run_risk_finder(db, document),
    ]
