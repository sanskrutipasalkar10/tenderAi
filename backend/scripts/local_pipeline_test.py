"""Local, DB-free pipeline test harness - for validating classify/extract/chunk
(zero info loss), map pass (chunk summarization completeness), and the go_no_go
reduce logic (correctness against a real company profile) WITHOUT the shared
Postgres. Built because Sapana's DB was unreachable and testing shouldn't block on it.

This is a diagnostic script, not a new pipeline path - it calls the exact same
functions production uses (classify_page, extract_page_text, extract_page_via_vision,
extract_table_structure, plan_chunk_ranges, complete_structured, check_hard_gates,
compute_weighted_score, decide), just with local files standing in for the `pages`/
`chunks`/`chunk_extractions` tables. LLM calls (map pass, go_no_go) still go out to
real Ollama Cloud/local per app/llm/client.py's own fallback - only Postgres is skipped.

Every stage writes its output to disk so gaps can be inspected by hand:

    <out>/pages/page_0001.txt              one file per page, classification + raw_text
    <out>/pages/EXTRACTION_GAPS.txt        pages with no text at all (if any)
    <out>/chunks/chunk_00_pages_1-5.txt    assembled chunk content, exactly as map_pass sees it
    <out>/chunks/COVERAGE_REPORT.txt       does every page appear in some chunk? (completeness)
    <out>/chunk_extractions/chunk_00.json  the real MapPassResult the model returned per chunk
    <out>/go_no_go_result.json             the real GoNoGoResult (same logic as reduce_pass.py)

Usage:
    PYTHONPATH="." .venv/Scripts/python.exe scripts/local_pipeline_test.py <pdf_path> \
        [--profile scripts/seed_data/c4i4_lab_profile.json] [--out <dir>] \
        [--skip-llm]   # stop after chunking; skip the two real LLM-calling stages
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.schemas import GoNoGoLLMResult, MapPassResult, PageExtractionResult  # noqa: E402
from app.pipeline.chunk import (  # noqa: E402
    CHUNK_OVERLAP_PAGES,
    CHUNK_SIZE_PAGES,
    plan_chunk_ranges,
)
from app.pipeline.classify import classification_confidence, classify_page  # noqa: E402
from app.pipeline.extract_native import extract_page_text, extract_table_structure  # noqa: E402
from app.pipeline.extract_vision import extract_page_via_vision  # noqa: E402
from app.pipeline.map_pass import _format_chunk_content  # noqa: E402
from app.pipeline.reduce_pass import (  # noqa: E402
    REQUIRED_PROFILE_FIELDS,
    check_hard_gates,
    compute_weighted_score,
    decide,
)
from app.prompts.registry import load_prompt  # noqa: E402

NATIVE_EXTRACTABLE_CLASSIFICATIONS = {"native_text", "table", "mixed"}

# Mirrors app/workers/tasks_reduce.py's _profile_to_dict EXACTLY (every field except
# unconfirmed_org_turnover_inr, deliberately excluded there and here) - inlined rather
# than imported because importing that module pulls in app.workers.celery_app
# (circular import through tasks_pipeline.py), which this DB-free script has no need
# for. Keep this field list in sync with the real one if it ever changes.
_PROFILE_TO_DICT_FIELDS = (
    "company_name", "annual_turnover", "turnover_source", "certifications",
    "past_projects", "geographic_presence", "sectors", "max_capacity_pct",
    "cin", "roc_number", "section8_licence_number", "date_of_incorporation",
    "pan", "gstin", "udyam_registration_number", "msme_classification",
    "ngo_darpan_id", "authorised_capital_inr", "paid_up_capital_inr",
    "net_worth_inr", "directors", "bank_details", "employment_count",
    "government_grants",
)


def _profile_to_dict(profile_raw: dict) -> dict:
    return {field: profile_raw.get(field) for field in _PROFILE_TO_DICT_FIELDS}


def stage1_extract(pdf_path: Path, out_dir: Path) -> dict[int, PageExtractionResult]:
    """Classify + extract every page, exactly as app/services/ingestion.py does per
    page, but writing to local files instead of the `pages` table. Returns a dict
    keyed by 1-indexed page number so stage 2 can look pages up by the same numbering
    plan_chunk_ranges uses internally (0-indexed) after a +1 shift.
    """
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    results: dict[int, PageExtractionResult] = {}
    gaps: list[str] = []

    print(f"[Stage 1] Classifying + extracting {doc.page_count} pages...")
    for page in doc:
        classification = classify_page(page)
        confidence = classification_confidence(page, classification)

        if classification in NATIVE_EXTRACTABLE_CLASSIFICATIONS:
            result = extract_page_text(page)
        else:
            result = extract_page_via_vision(page)

        results[page.number] = result

        page_num_1indexed = page.number + 1
        header = (
            f"page_number: {page_num_1indexed}\n"
            f"classification: {classification}\n"
            f"confidence: {confidence:.2f}\n"
            f"extraction_method: {result.extraction_method}\n"
            f"---\n"
        )
        text = result.raw_text or ""
        (pages_dir / f"page_{page_num_1indexed:04d}.txt").write_text(
            header + text, encoding="utf-8"
        )

        if not text.strip():
            gaps.append(
                f"page {page_num_1indexed}: EMPTY raw_text "
                f"(classification={classification}, method={result.extraction_method})"
            )

        if classification == "table":
            table = extract_table_structure(pdf_path, page.number)
            if table is not None:
                (pages_dir / f"page_{page_num_1indexed:04d}_table.json").write_text(
                    json.dumps(table.model_dump(), indent=2), encoding="utf-8"
                )

    gap_report = pages_dir / "EXTRACTION_GAPS.txt"
    if gaps:
        gap_report.write_text("\n".join(gaps), encoding="utf-8")
        print(f"  WARNING: {len(gaps)} page(s) with NO extracted text - see {gap_report}")
    else:
        gap_report.write_text(
            "No gaps - every page produced non-empty raw_text.\n", encoding="utf-8"
        )
        print(f"  OK - all {doc.page_count} pages produced non-empty raw_text. No gaps.")

    doc.close()
    return results


def stage2_chunk(
    pdf_path: Path, page_results: dict[int, PageExtractionResult], out_dir: Path
) -> list[tuple[int, int]]:
    """Plans chunk ranges the same way build_chunks does (plan_chunk_ranges is pure,
    no DB), assembles each chunk's content from stage 1's local page files via the
    real _format_chunk_content, and verifies every page appears in at least one
    chunk - the completeness check for "tender should be chunked completely, no info
    loss."
    """
    chunks_dir = out_dir / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    doc.close()

    ranges = plan_chunk_ranges(total_pages, CHUNK_SIZE_PAGES, CHUNK_OVERLAP_PAGES)
    print(f"[Stage 2] Planned {len(ranges)} chunks over {total_pages} pages "
          f"(size={CHUNK_SIZE_PAGES}, overlap={CHUNK_OVERLAP_PAGES})...")

    covered_pages: set[int] = set()
    for i, (start, end) in enumerate(ranges):
        pages_in_range = [
            (n + 1, page_results[n].raw_text)
            for n in range(start, end + 1)
            if n in page_results and page_results[n].raw_text
        ]
        covered_pages.update(n for n, _ in pages_in_range)
        content = _format_chunk_content(pages_in_range)
        (chunks_dir / f"chunk_{i:02d}_pages_{start + 1}-{end + 1}.txt").write_text(
            content, encoding="utf-8"
        )

    all_pages = set(range(1, total_pages + 1))
    missing = sorted(all_pages - covered_pages)
    report_lines = [
        f"Total pages: {total_pages}",
        f"Chunks planned: {len(ranges)}",
        f"Pages covered by at least one chunk: {len(covered_pages)}/{total_pages}",
    ]
    if missing:
        report_lines.append(f"GAP - pages missing from every chunk: {missing}")
        print(f"  WARNING: {len(missing)} page(s) not covered by any chunk: {missing}")
    else:
        report_lines.append("No gaps - every extracted page is covered by at least one chunk.")
        print(f"  OK - all {len(covered_pages)} extracted pages are covered by the chunk plan.")
    (chunks_dir / "COVERAGE_REPORT.txt").write_text("\n".join(report_lines), encoding="utf-8")

    return ranges


def stage3_map_pass(out_dir: Path, num_chunks: int) -> list[MapPassResult]:
    """Runs the REAL map-pass prompt + complete_structured("map", ...) against each
    local chunk file - a genuine Ollama Cloud/local call, same as production, just
    reading/writing local files instead of chunks/chunk_extractions.
    """
    from app.llm.structured import complete_structured

    chunks_dir = out_dir / "chunks"
    extractions_dir = out_dir / "chunk_extractions"
    extractions_dir.mkdir(parents=True, exist_ok=True)

    chunk_files = sorted(chunks_dir.glob("chunk_*.txt"))
    print(f"[Stage 3] Running real map-pass LLM calls on {len(chunk_files)} chunks "
          f"(this hits Ollama for real - expect ~1-2 min per chunk)...")

    results: list[MapPassResult] = []
    for i, chunk_file in enumerate(chunk_files):
        content = chunk_file.read_text(encoding="utf-8")
        if not content.strip():
            print(f"  [{i + 1}/{len(chunk_files)}] {chunk_file.name}: empty, skipping LLM call")
            result = MapPassResult()
            model_used = None
        else:
            prompt = load_prompt("map_pass", "v1_map_pass").replace("{content}", content)
            result, model_used = complete_structured("map", prompt, MapPassResult)
            print(
                f"  [{i + 1}/{len(chunk_files)}] {chunk_file.name}: "
                f"{len(result.criteria)} criteria, {len(result.dates)} dates, "
                f"{len(result.amounts)} amounts, {len(result.risk_candidates)} risks "
                f"(model={model_used})"
            )

        out_path = extractions_dir / (chunk_file.stem + ".json")
        out_path.write_text(
            json.dumps({"model_used": model_used, "result": result.model_dump()}, indent=2),
            encoding="utf-8",
        )
        results.append(result)

    return results


def stage4_go_no_go(
    chunk_extractions: list[MapPassResult], profile_path: Path, out_dir: Path
) -> None:
    """Runs the REAL go_no_go decision logic - same aggregation, same prompt, same
    check_hard_gates/compute_weighted_score/decide code reduce_pass.py uses - against
    a company profile loaded from a local JSON file instead of the company_profiles
    table. _profile_to_dict is the exact production function that decides what subset
    of the profile the LLM sees.
    """
    from app.llm.structured import complete_structured

    print(f"[Stage 4] Aggregating {len(chunk_extractions)} chunk extractions and "
          f"running the real go_no_go decision logic...")

    aggregated = MapPassResult()
    for r in chunk_extractions:
        aggregated.dates.extend(r.dates)
        aggregated.amounts.extend(r.amounts)
        aggregated.criteria.extend(r.criteria)
        aggregated.risk_candidates.extend(r.risk_candidates)

    profile_raw = json.loads(profile_path.read_text(encoding="utf-8"))
    profile_dict = _profile_to_dict(profile_raw)

    missing = [f for f in REQUIRED_PROFILE_FIELDS if profile_dict.get(f) is None]
    if missing:
        print(f"  Profile is missing required fields {missing} - would short-circuit "
              f"to Conditional-Go (Partner Required) with no LLM call in production.")
        result = {
            "score": 0, "decision": "Conditional-Go (Partner Required)",
            "criteria_matches": [], "gaps": missing, "next_steps": [], "factor_scores": None,
        }
    elif not aggregated.criteria:
        print("  No eligibility criteria found across any chunk - would short-circuit "
              "to Conditional-Go (Partner Required) with no LLM call in production.")
        result = {
            "score": 0, "decision": "Conditional-Go (Partner Required)",
            "criteria_matches": [], "gaps": ["No eligibility criteria found in document"],
            "next_steps": [], "factor_scores": None,
        }
    else:
        content = "\n".join(f"[PAGE {c.page_ref}] {c.description}" for c in aggregated.criteria)
        profile_text = "\n".join(f"{k}: {v}" for k, v in profile_dict.items())
        prompt = (
            load_prompt("reduce", "v1_go_no_go")
            .replace("{company_profile}", profile_text)
            .replace("{content}", content)
        )
        llm_result, model_used = complete_structured("reduce", prompt, GoNoGoLLMResult)

        triggered_gates = check_hard_gates(llm_result.criteria_matches)
        weighted_score = compute_weighted_score(llm_result.factor_scores)
        decision = "No-Go" if triggered_gates else decide(weighted_score)
        result = {
            "score": round(weighted_score),
            "decision": decision,
            "criteria_matches": [m.model_dump() for m in llm_result.criteria_matches],
            "gaps": triggered_gates,
            "next_steps": llm_result.next_steps,
            "factor_scores": llm_result.factor_scores,
            "model_used": model_used,
        }
        print(f"  Decision: {result['decision']} | Score: {result['score']}")
        print(f"  Factor scores: {result['factor_scores']}")
        print(f"  Triggered gates: {triggered_gates or 'none'}")

    (out_dir / "go_no_go_result.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument(
        "--profile", type=Path,
        default=Path(__file__).parent / "seed_data" / "c4i4_lab_profile.json",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="Stop after chunking (stages 1-2 only) - no Ollama calls, no cost/wait.",
    )
    args = parser.parse_args()

    out_dir = args.out or Path(__file__).parent / "local_pipeline_test_output" / args.pdf_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {out_dir}\n")

    page_results = stage1_extract(args.pdf_path, out_dir)
    print()
    stage2_chunk(args.pdf_path, page_results, out_dir)
    print()

    if args.skip_llm:
        print("--skip-llm set - stopping before the two LLM-calling stages.")
        return

    chunk_extractions = stage3_map_pass(out_dir, len(page_results))
    print()
    stage4_go_no_go(chunk_extractions, args.profile, out_dir)
    print(f"\nAll output written to: {out_dir}")


if __name__ == "__main__":
    main()
