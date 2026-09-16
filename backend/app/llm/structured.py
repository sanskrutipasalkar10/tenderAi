"""Structured-output enforcement — gets valid, schema-conformant JSON out of a model,
with retry on parse/validation failure (CLAUDE.md hard rule 4: every LLM output is
validated by a Pydantic model). Sits on top of app.llm.client.complete_for_task, so
callers (map_pass.py, reduce_pass.py) never handle raw JSON parsing themselves.
"""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.llm.client import complete_for_task
from app.llm.router import Task

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

DEFAULT_MAX_PARSE_RETRIES = 2


def complete_structured(
    task: Task,
    prompt: str,
    schema: type[T],
    *,
    image_bytes: bytes | None = None,
    max_parse_retries: int = DEFAULT_MAX_PARSE_RETRIES,
) -> tuple[T, str]:
    """Calls the model for `task` and parses+validates its response against `schema`,
    retrying (same prompt, a fresh call) on invalid JSON or a schema mismatch — a model
    occasionally wraps JSON in prose or omits a field, and a retry usually fixes it
    without needing prompt-engineering gymnastics.

    Returns (validated_object, model_that_produced_it) — same provenance pattern as
    complete_for_task, since a parse retry (or the cloud->local fallback inside
    complete_for_task) can mean a different model served the final, valid response
    than the one first attempted.

    Raises ProviderError if the model never returns valid `schema` JSON within
    `max_parse_retries + 1` attempts, or if complete_for_task itself fails (cloud and
    local fallback both down).
    """
    last_error: Exception | None = None
    for attempt in range(max_parse_retries + 1):
        raw_text, model_used = complete_for_task(
            task,
            prompt,
            image_bytes=image_bytes,
            response_format={"type": "json_object"},
        )
        try:
            data = _extract_json(raw_text)
            return schema.model_validate(data), model_used
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            logger.warning(
                "llm.structured_parse_retry",
                task=task,
                model=model_used,
                schema=schema.__name__,
                attempt=attempt + 1,
                error=str(exc),
            )

    logger.error(
        "llm.structured_parse_failed",
        task=task,
        schema=schema.__name__,
        attempts=max_parse_retries + 1,
        error=str(last_error),
    )
    raise ProviderError(
        f"Model never returned valid {schema.__name__} JSON for task={task!r} "
        f"after {max_parse_retries + 1} attempts: {last_error}"
    )


def _extract_json(text: str) -> dict:
    """Models sometimes wrap JSON in a markdown code fence or add a sentence before/
    after it despite being asked for JSON only — try the raw text first, then the
    largest {...} span, before giving up and letting the caller's retry loop handle it.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise json.JSONDecodeError("No JSON object found in response", text, 0)
