"""The Synopsis "About Project" brief (docs/DECISIONS.md #92) — what the tender wants
built/supplied, the technical requirements it states, and an AI-suggested way to
execute it.

Unlike every other synopsis field, this is written from the tender's own page TEXT,
not from map-pass facts: the map pass only extracts dates/amounts/eligibility
criteria/risks/documents, so a brief written from those would be guessing the
project's scope from who's allowed to bid. A rule-based page selector (hard rule 3 —
code, not a prompt) drops GeM's standard terms pages, sends every remaining page when
they fit the budget, and otherwise picks the pages under scope/specification-style
headings — to the fast/cheap "project_brief" model tier (app.llm.router). Pages are
read from the `pages` table, so Reevaluate regenerates the brief for an
already-processed tender without re-ingesting.

This is deterministic page selection inside one document, not retrieval — there is no
index, embedding, or query; CLAUDE.md's "no retrieval step" rule is about not building
a RAG layer, which this isn't.

Never fails the synopsis: any provider/parse failure returns None and the frontend
offers a Reevaluate instead (same degrade-don't-fail pattern as _run_pq_checklist).
"""

import re
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.llm.structured import complete_structured
from app.models.document import Document
from app.models.schemas import ProjectBrief, ProjectBriefLLMResult
from app.pipeline.tender_pages import is_standard_terms_page, load_tender_pages
from app.prompts.registry import load_prompt

logger = get_logger(__name__)

# Ordered most- to least-specific: when the page budget runs out, a page under
# "Scope of Work" wins over one that merely has a "Background" heading.
_HEADING_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bscope\s+of\s+(the\s+)?(work|works|project|services|supply|contract)\b",
        # Corrigenda/amendments change the tender itself — on GeM bids they're often
        # the only place the real nature of the work shows (docs/DECISIONS.md #92).
        r"\b(corrigendum|addendum|amendments?|revised\s+provision)\b",
        r"\bstatement\s+of\s+work\b",
        r"\bterms\s+of\s+reference\b",
        r"\btechnical\s+(specifications?|requirements?|particulars)\b",
        r"\bfunctional\s+requirements?\b",
        r"\bschedule\s+of\s+requirements?\b",
        r"\b(brief\s+)?description\s+of\s+(the\s+)?(work|works|project|services)\b",
        r"\bproject\s+(overview|background|description|details|profile)\b",
        r"\bname\s+of\s+(the\s+)?work\b",
        r"\bdeliverables\b",
        r"\bbill\s+of\s+quantit(y|ies)\b",
        r"\bcatalogue\s+values\b",
        r"\bobjectives?\s+of\s+(the\s+)?(project|assignment|work)\b",
        r"\bbackground\b",
    )
)
# A heading is a short line; a long line that happens to contain "scope of work" is
# usually a clause *referring* to the scope, not the section itself.
_MAX_HEADING_LINE_CHARS = 100
# Table-of-contents lines ("Scope of Work ........ 12") point AT the section; picking
# the contents page would spend budget on a page that says nothing about the project.
_TOC_LINE = re.compile(r"(\.{3,}|…+|\s{3,})\s*\d{1,4}\s*$")

# How many pages after a matched heading belong to that section, in practice.
_FOLLOWING_PAGES = 2
# Budget for one call: ~60k chars is ~15k tokens of input on the cheap tier.
_MAX_PAGES = 20
_MAX_TOTAL_CHARS = 60_000
_MAX_CHARS_PER_PAGE = 6_000
# No heading matched at all: a tender's opening pages (NIT/cover/introduction) are the
# next-best description of what it's for.
_FALLBACK_PAGES = 8

def build_project_brief(db: Session, document: Document) -> ProjectBrief | None:
    pages = load_tender_pages(db, document)
    selected = select_project_pages(pages)
    if not selected:
        logger.warning("project_brief.no_page_text", document_id=str(document.id))
        return None

    prompt = load_prompt("reduce", "v1_project_brief").replace(
        "{content}", _format_pages(selected)
    )
    try:
        llm_result, _ = complete_structured("project_brief", prompt, ProjectBriefLLMResult)
    except ProviderError:
        logger.warning("project_brief.failed", document_id=str(document.id))
        return None

    source_pages = [number for number, _ in selected]
    return _keep_only_shown_pages(llm_result, source_pages, str(document.id))


def select_project_pages(pages: Sequence[tuple[int, str]]) -> list[tuple[int, str]]:
    """The tender's own pages, in page order. When they all fit the char budget (most
    GeM bids, and any short tender) every one is sent — nothing about the project can
    be missed by a heading the selector didn't anticipate. Larger tenders get the pages
    under scope/specification headings (plus the pages that follow each), most-specific
    heading first, within the page/char budget.
    """
    text_by_page = {
        number: text
        for number, text in pages
        if text and text.strip() and not is_standard_terms_page(text)
    }
    page_numbers = sorted(text_by_page)

    if sum(min(len(t), _MAX_CHARS_PER_PAGE) for t in text_by_page.values()) <= _MAX_TOTAL_CHARS:
        return [(number, text_by_page[number][:_MAX_CHARS_PER_PAGE]) for number in page_numbers]

    seeds = sorted(
        (rank, number)
        for number in page_numbers
        if (rank := _best_heading_rank(text_by_page[number])) is not None
    )
    if seeds:
        candidates: list[int] = []
        for _, number in seeds:
            start = page_numbers.index(number)
            candidates.extend(page_numbers[start : start + 1 + _FOLLOWING_PAGES])
    else:
        candidates = page_numbers[:_FALLBACK_PAGES]

    chosen: list[int] = []
    total_chars = 0
    for number in candidates:
        if number in chosen:
            continue
        page_chars = min(len(text_by_page[number]), _MAX_CHARS_PER_PAGE)
        if len(chosen) >= _MAX_PAGES or total_chars + page_chars > _MAX_TOTAL_CHARS:
            break
        chosen.append(number)
        total_chars += page_chars

    return [(number, text_by_page[number][:_MAX_CHARS_PER_PAGE]) for number in sorted(chosen)]


def _best_heading_rank(text: str) -> int | None:
    best: int | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > _MAX_HEADING_LINE_CHARS or _TOC_LINE.search(line):
            continue
        for rank, pattern in enumerate(_HEADING_PATTERNS):
            if pattern.search(line) and (best is None or rank < best):
                best = rank
                break
    return best


def _keep_only_shown_pages(
    llm_result: ProjectBriefLLMResult, source_pages: list[int], document_id: str
) -> ProjectBrief:
    """A page_ref the model wasn't shown can't be a real citation — drop it rather than
    render a link to a page that never said this (zero-hallucination rule for anything
    presented as coming from the tender). The AI-suggested sections carry no page_refs.
    """
    allowed = set(source_pages)
    requirements = [r for r in llm_result.technical_requirements if r.page_ref in allowed]
    about_page_refs = sorted({p for p in llm_result.about_project_page_refs if p in allowed})
    dropped = len(llm_result.technical_requirements) - len(requirements)
    if dropped:
        logger.warning(
            "project_brief.dropped_uncited_requirements", document_id=document_id, dropped=dropped
        )
    return ProjectBrief(
        **llm_result.model_dump(exclude={"technical_requirements", "about_project_page_refs"}),
        technical_requirements=requirements,
        about_project_page_refs=about_page_refs,
        source_pages=source_pages,
    )


def _format_pages(pages: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"[PAGE {number}]\n{text}" for number, text in pages)
