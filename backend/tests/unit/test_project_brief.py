"""Unit tests for app.pipeline.project_brief — page selection is pure code; the LLM is
mocked at complete_structured and page loading at _load_pages (CLAUDE.md hard rule 8).
"""

import uuid

from app.core.exceptions import ProviderError
from app.models.document import Document
from app.models.schemas import (
    ProjectApproachStep,
    ProjectBriefLLMResult,
    ProjectTechnicalRequirement,
)
from app.pipeline import project_brief
from app.pipeline.project_brief import select_project_pages


def _filler(n: int) -> str:
    # ~3.4k chars, a realistic page: 20 of them exceed the 60k budget, so heading
    # selection (not "send everything") is what these tests exercise.
    return f"General conditions of contract, clause {n}. " * 70


# --- page selection ----------------------------------------------------------------


def test_selects_the_scope_heading_page_and_the_pages_after_it() -> None:
    pages = [(i, _filler(i)) for i in range(30)]
    pages[10] = (10, "SECTION 4\nSCOPE OF WORK\nThe contractor shall install 40 CCTV cameras.")

    selected = select_project_pages(pages)

    assert [n for n, _ in selected] == [10, 11, 12]


def test_ignores_table_of_contents_lines() -> None:
    pages = [(i, _filler(i)) for i in range(30)]
    pages[1] = (1, "CONTENTS\nScope of Work ............ 14\nTechnical Specifications ..... 16")
    pages[14] = (14, "Scope of Work\nSupply and installation of solar pumps.")

    selected = [n for n, _ in select_project_pages(pages)]

    assert 1 not in selected
    assert selected[0] == 14


def test_a_long_sentence_mentioning_scope_is_not_a_heading() -> None:
    sentence = (
        "Any change to the scope of work shall be approved in writing by the Engineer-in-"
        "Charge before execution, failing which no payment will be made for it."
    )
    pages = [(0, _filler(0)), (1, sentence), (2, _filler(2))]

    # No heading anywhere -> falls back to the opening pages, not "page 1 matched".
    assert [n for n, _ in select_project_pages(pages)] == [0, 1, 2]


def test_falls_back_to_the_opening_pages_when_no_heading_matches() -> None:
    pages = [(i, _filler(i)) for i in range(30)]

    assert [n for n, _ in select_project_pages(pages)] == list(range(8))


def test_more_specific_headings_win_when_the_budget_is_tight(monkeypatch) -> None:
    monkeypatch.setattr(project_brief, "_MAX_PAGES", 3)
    pages = [(i, _filler(i)) for i in range(40)]
    pages[2] = (2, "1. Background\nThe department runs 12 hospitals.")
    pages[30] = (30, "Scope of Work\nBuild a hospital information system.")

    assert [n for n, _ in select_project_pages(pages)] == [30, 31, 32]


def test_respects_the_total_character_budget(monkeypatch) -> None:
    monkeypatch.setattr(project_brief, "_MAX_TOTAL_CHARS", 1000)
    pages = [(i, "Scope of Work\n" + "x" * 600) for i in range(10)]

    assert len(select_project_pages(pages)) == 1


def test_sends_every_page_when_the_tender_fits_the_budget() -> None:
    # A real GeM bid: no page under a recognisable heading says what's being bought,
    # but the corrigendum (page 10) does — it must not be dropped.
    pages = [(i, f"Bid details page {i}") for i in range(10)]
    pages.append((10, "Additional Information\nVoice platform scale (minutes per month)"))

    assert [n for n, _ in select_project_pages(pages)] == list(range(11))


def test_drops_gem_standard_terms_pages() -> None:
    pages = [
        (0, "Bid Details\nAI voice platform for the farmers' helpline"),
        (1, "General Terms and Conditions on GeM 4.0 (Version 1.29)\n1. Scope of Contract"),
    ]

    assert [n for n, _ in select_project_pages(pages)] == [0]


def test_skips_pages_without_text() -> None:
    pages = [(0, ""), (1, "   "), (2, "Terms of Reference\nDesign a dashboard.")]

    assert [n for n, _ in select_project_pages(pages)] == [2]


# --- build_project_brief -----------------------------------------------------------


def _document() -> Document:
    return Document(id=uuid.uuid4(), filename="x.pdf", status="analyzing")


def _llm_result(**overrides) -> ProjectBriefLLMResult:
    return ProjectBriefLLMResult(
        **{
            "about_project": "Supply and install 40 CCTV cameras across Pune.",
            "about_project_page_refs": [3],
            "technical_requirements": [
                ProjectTechnicalRequirement(
                    category="Hardware", requirement="4 MP IP cameras", page_ref=3
                )
            ],
            "suggested_approach": [
                ProjectApproachStep(phase="Site survey", description="Survey all 40 sites.")
            ],
            **overrides,
        }
    )


def test_calls_the_cheap_tier_with_only_the_selected_pages(monkeypatch) -> None:
    pages = [(i, _filler(i)) for i in range(30)]
    pages[3] = (3, "Scope of Work\nSupply and install 40 CCTV cameras.")
    monkeypatch.setattr(project_brief, "load_tender_pages", lambda db, doc: pages)
    calls = []

    def _fake(task, prompt, schema):
        calls.append((task, prompt))
        return _llm_result(), "test-model"

    monkeypatch.setattr(project_brief, "complete_structured", _fake)

    brief = project_brief.build_project_brief(None, _document())

    assert brief is not None
    assert brief.source_pages == [3, 4, 5]
    task, prompt = calls[0]
    assert task == "project_brief"
    assert "[PAGE 3]" in prompt and "[PAGE 6]" not in prompt
    assert "{content}" not in prompt


def test_drops_requirements_citing_a_page_the_model_was_not_shown(monkeypatch) -> None:
    pages = [(3, "Scope of Work\nInstall cameras."), (4, "more"), (5, "more")]
    monkeypatch.setattr(project_brief, "load_tender_pages", lambda db, doc: pages)
    invented = ProjectTechnicalRequirement(category="Software", requirement="VMS", page_ref=99)
    real = ProjectTechnicalRequirement(category="Hardware", requirement="4 MP", page_ref=4)
    monkeypatch.setattr(
        project_brief,
        "complete_structured",
        lambda *a, **k: (
            _llm_result(technical_requirements=[invented, real], about_project_page_refs=[3, 99]),
            "m",
        ),
    )

    brief = project_brief.build_project_brief(None, _document())

    assert brief is not None
    assert [r.requirement for r in brief.technical_requirements] == ["4 MP"]
    assert brief.about_project_page_refs == [3]
    # The AI-suggested sections carry no citations, so nothing is filtered there.
    assert brief.suggested_approach[0].phase == "Site survey"


def test_returns_none_instead_of_raising_when_the_llm_fails(monkeypatch) -> None:
    monkeypatch.setattr(
        project_brief, "load_tender_pages", lambda db, doc: [(0, "Scope of Work\nBuild a road.")]
    )

    def _fail(*a, **k):
        raise ProviderError("down")

    monkeypatch.setattr(project_brief, "complete_structured", _fail)

    assert project_brief.build_project_brief(None, _document()) is None


def test_returns_none_without_calling_the_llm_when_no_page_has_text(monkeypatch) -> None:
    monkeypatch.setattr(project_brief, "load_tender_pages", lambda db, doc: [])
    monkeypatch.setattr(
        project_brief,
        "complete_structured",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not call LLM")),
    )

    assert project_brief.build_project_brief(None, _document()) is None
