"""Provider access layer — the ONLY file in this codebase allowed to name a provider or
call one directly (CLAUDE.md hard rule 1). Every retry/backoff/timeout policy for every
provider call lives here once (hard rule 10), not duplicated across map_pass.py,
reduce_pass.py, and extract_vision.py.

Every model this project currently routes to is Ollama (cloud or local — see
app.llm.router), called via Ollama's native /api/chat, NOT litellm. This wasn't the
original design (see docs/DECISIONS.md #29 for the first litellm/Ollama bug found —
image handling); it's now the case for text calls too after a second, more serious bug
(docs/DECISIONS.md #34): litellm's `timeout` parameter is not reliably enforced against
the ollama_chat provider for large prompts — a real chunk from a real tender document
hung well past its configured timeout with no error, a genuine CLAUDE.md hard-rule-10
violation (every external call must have an enforced timeout). `requests`' own timeout
is reliably enforced, so that's what every call goes through now. litellm stays a
dependency (imported, available) in case a genuinely non-Ollama provider is ever added
— complete() still branches on provider prefix, it just happens that 100% of traffic
takes the Ollama branch today.
"""

import base64
import random
import time
from typing import Any

import requests

from app.core.config import settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.core.tracing import trace_llm_call
from app.llm import router

logger = get_logger(__name__)

DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_NUM_RETRIES = 1


def complete(
    model: str,
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    response_format: dict | None = None,
    temperature: float = 0.0,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    num_retries: int = DEFAULT_NUM_RETRIES,
) -> str:
    """Calls the given model with a text prompt and an optional image.

    `model` is always resolved by app.llm.router, never hardcoded by a caller. Returns
    the raw text response; schema validation of that text happens in
    app.llm.structured, not here.

    Raises ProviderError (never a raw requests/provider exception) on failure, after
    bounded retry-with-backoff is exhausted.
    """
    if model.startswith("ollama/") or model.startswith("ollama_chat/"):
        return _complete_ollama_native(
            model,
            prompt,
            image_bytes=image_bytes,
            response_format=response_format,
            temperature=temperature,
            timeout=timeout,
            num_retries=num_retries,
        )

    raise ProviderError(
        f"No non-Ollama provider is configured — got model={model!r}. "
        "Add a branch here (and its own retry/timeout handling) before routing to it."
    )


def complete_for_task(
    task: router.Task,
    prompt: str,
    *,
    image_bytes: bytes | None = None,
    response_format: dict | None = None,
    temperature: float = 0.0,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    num_retries: int = DEFAULT_NUM_RETRIES,
) -> tuple[str, str]:
    """Calls the primary (Ollama Cloud) model for `task`; on failure, automatically
    falls back to a genuinely local Ollama model for the same task (docs/DECISIONS.md
    #32) rather than letting a transient cloud outage/rate-limit stop the pipeline.

    Returns (response_text, model_that_actually_served_it) — callers that record
    provenance (e.g. extract_vision.py's extraction_method: vision_cloud vs
    vision_local) need to know which one actually ran, not just which was attempted
    first.

    This is what pipeline code (extract_vision.py, map_pass.py, and reduce_pass.py)
    should call — not complete() + router.route() directly — unless a caller
    specifically needs one exact model with no fallback (e.g. a test).

    Traced via app.core.tracing (docs/DECISIONS.md #52) — one Langfuse generation per
    call, tagged with `task` and whether the fallback path was used, regardless of
    outcome.
    """
    with trace_llm_call(task=task, prompt=prompt) as trace_result:
        primary = router.route(task)
        try:
            output = complete(
                primary,
                prompt,
                image_bytes=image_bytes,
                response_format=response_format,
                temperature=temperature,
                timeout=timeout,
                num_retries=num_retries,
            )
            trace_result["model"] = primary
            trace_result["output"] = output
            return output, primary
        except ProviderError as exc:
            fallback = router.route_fallback(task)
            if fallback == primary:
                # settings.use_local_vision already made the primary the local model —
                # nothing further to fall back to.
                trace_result["error"] = str(exc)
                raise
            logger.warning(
                "llm.falling_back_to_local",
                task=task,
                primary=primary,
                fallback=fallback,
                error=str(exc),
            )
            try:
                output = complete(
                    fallback,
                    prompt,
                    image_bytes=image_bytes,
                    response_format=response_format,
                    temperature=temperature,
                    timeout=timeout,
                    num_retries=num_retries,
                )
                trace_result["model"] = fallback
                trace_result["output"] = output
                trace_result["fallback_used"] = True
                return output, fallback
            except ProviderError as fallback_exc:
                trace_result["error"] = str(fallback_exc)
                trace_result["fallback_used"] = True
                raise


def _complete_ollama_native(
    model: str,
    prompt: str,
    *,
    image_bytes: bytes | None,
    response_format: dict | None,
    temperature: float,
    timeout: int,
    num_retries: int,
) -> str:
    """Calls Ollama's native /api/chat directly. Same api_base whether the model tag
    is a local model or an Ollama-cloud-hosted "...:cloud" one — Ollama's local daemon
    transparently proxies :cloud tags.
    """
    ollama_model = model.split("/", 1)[1]  # strip "ollama/" or "ollama_chat/" prefix

    message: dict[str, Any] = {"role": "user", "content": prompt}
    if image_bytes is not None:
        message["images"] = [base64.b64encode(image_bytes).decode("ascii")]

    payload: dict[str, Any] = {
        "model": ollama_model,
        "messages": [message],
        "stream": False,
        "options": {"temperature": temperature},
    }
    if response_format is not None and response_format.get("type") == "json_object":
        payload["format"] = "json"

    last_error: Exception | None = None
    for attempt in range(num_retries + 1):
        try:
            response = requests.post(
                f"{settings.ollama_base_url}/api/chat", json=payload, timeout=timeout
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}")
            response.raise_for_status()
            return response.json()["message"]["content"]
        except (requests.RequestException, KeyError) as exc:
            last_error = exc
            if attempt < num_retries:
                backoff = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "llm.ollama_retry",
                    model=model,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.error("llm.call_failed_after_retries", model=model, error=str(last_error))
    raise ProviderError(f"{model} unavailable after {num_retries} retries: {last_error}")
