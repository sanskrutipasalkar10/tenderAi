"""Langfuse tracing — self-hosted (docs/DECISIONS.md #52, asked of and confirmed by
the user rather than assumed: traces carry real prompt content, i.e. real tender
text, so this stays on infrastructure this project controls, never a cloud tracing
service). Wraps `app.llm.client.complete_for_task` — the one function every pipeline
stage (map_pass.py, reduce_pass.py, extract_vision.py) already calls (hard rule 1) —
so every real LLM call is traced for free, with no per-call-site instrumentation
needed in any of those three files.

A tracing failure must never break the pipeline — the same lesson Phase 5 learned the
hard way about structlog crashing on Windows (docs/DECISIONS.md #41). Every Langfuse
SDK call here is wrapped in try/except, logging a warning and continuing rather than
propagating; the `trace_llm_call` context manager itself never raises.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from langfuse import Langfuse

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# None when Langfuse isn't configured (no keys in .env) — every call below no-ops in
# that case rather than trying to reach a host that was never set up. Matches how
# settings.langfuse_public_key/secret_key already default to "" (Phase 0).
_client: Langfuse | None = None
if settings.langfuse_public_key and settings.langfuse_secret_key:
    try:
        _client = Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    except Exception as exc:  # noqa: BLE001 - tracing setup must never break startup
        logger.warning("tracing.client_init_failed", error=str(exc))


@contextmanager
def trace_llm_call(*, task: str, prompt: str) -> Iterator[dict]:
    """Wraps one app.llm.client.complete_for_task call. The caller fills the yielded
    dict in with `model`/`output`/`fallback_used` on success, or `error` on failure,
    before the context exits — either way, one Langfuse generation is recorded with
    real latency, so a failed call is just as visible as a successful one.
    """
    if _client is None:
        yield {}
        return

    start = time.monotonic()
    result: dict = {}
    try:
        yield result
    finally:
        _record_generation(task, prompt, result, time.monotonic() - start)


def _record_generation(task: str, prompt: str, result: dict, latency_seconds: float) -> None:
    if _client is None:
        return
    try:
        _client.generation(
            name=f"llm.{task}",
            model=result.get("model"),
            input=prompt,
            output=result.get("output"),
            level="ERROR" if result.get("error") else "DEFAULT",
            status_message=result.get("error"),
            metadata={
                "task": task,
                "latency_seconds": round(latency_seconds, 2),
                "fallback_used": result.get("fallback_used", False),
            },
        )
    except Exception as exc:  # noqa: BLE001 - tracing must never break the pipeline
        logger.warning("tracing.generation_failed", task=task, error=str(exc))


def flush() -> None:
    """Blocks until queued trace events are sent — call at worker/process shutdown
    (Langfuse batches and sends asynchronously otherwise, so events can be lost if the
    process exits first). No-op when tracing isn't configured.
    """
    if _client is not None:
        try:
            _client.flush()
        except Exception as exc:  # noqa: BLE001 - tracing must never break shutdown
            logger.warning("tracing.flush_failed", error=str(exc))
