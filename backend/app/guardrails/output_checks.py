"""Output-side guardrail (CLAUDE.md hard rule 6): rejects any document_analysis.result
that doesn't match its module's expected schema, regardless of what a reduce-pass model
actually returned. This is the last gate before a result is persisted — a malicious or
malformed tender could get an LLM to echo unexpected content, but it can never make that
content escape the fixed {go_no_go, synopsis, risk_finder} schemas defined in
app.models.schemas.
"""

from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.exceptions import DataQualityError
from app.models.document_analysis import ANALYSIS_MODULES
from app.models.schemas import GoNoGoResult, RiskFinderResult, SynopsisResult

_SCHEMA_BY_MODULE: dict[str, type[BaseModel]] = {
    "go_no_go": GoNoGoResult,
    "synopsis": SynopsisResult,
    "risk_finder": RiskFinderResult,
}


def validate_analysis_result(module: str, result: dict[str, Any]) -> dict[str, Any]:
    """Validates `result` against `module`'s fixed schema and returns it re-serialized
    from the validated model (never the raw dict) — so anything outside the schema,
    however it got there, is dropped rather than persisted.
    """
    if module not in ANALYSIS_MODULES:
        raise DataQualityError(f"Unknown document_analysis module: {module!r}")

    schema = _SCHEMA_BY_MODULE[module]
    try:
        validated = schema.model_validate(result)
    except ValidationError as exc:
        raise DataQualityError(
            f"{module} result does not match the expected schema: {exc}"
        ) from exc
    return validated.model_dump()
