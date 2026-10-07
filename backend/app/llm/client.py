"""Provider access layer — the ONLY file in this codebase allowed to name a provider or
call one directly (CLAUDE.md hard rule 1). Every retry/backoff/timeout policy for every
provider call lives here once (hard rule 10), not duplicated across map_pass.py,
reduce_pass.py, and extract_vision.py.

Two providers now (docs/DECISIONS.md #76): Gemini (primary, `gemini/` prefix) and
Ollama (fallback — cloud tag or local, `ollama/`/`ollama_chat/` prefix, see
app.llm.router). Both go through native REST via `requests`, NOT litellm/an SDK —
the Ollama path already had two confirmed litellm bugs (docs/DECISIONS.md #29 image
handling, #34 `timeout` not reliably enforced for large prompts — a real hard-rule-10
violation), so the same "call the provider's own REST API directly, hand-roll
timeout/retry" pattern is used for Gemini too, for consistency and because it avoids
introducing a new SDK dependency and its own unverified quirks. litellm stays a
dependency (imported, available) in case a genuinely different provider is ever added
— complete() still branches on provider prefix, it just happens that no current
traffic takes the litellm branch.
"""

import base64
import json
import random
import time
from collections.abc import Callable, Iterator
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
# Vertex AI "Express Mode" (docs/DECISIONS.md #76) — this project's Gemini API key is
# an Express-mode key (the "AQ." prefix, confirmed by direct testing: it 403s against
# the AI Studio host generativelanguage.googleapis.com with API_KEY_SERVICE_BLOCKED,
# and only authenticates against aiplatform.googleapis.com). A plain AI-Studio key
# (the more commonly documented "AIzaSy..." format) would need the AI Studio host
# instead — this project's key is the Express-mode kind, so that's what's wired here.
GEMINI_API_BASE = "https://aiplatform.googleapis.com/v1/publishers/google/models"


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
    if model.startswith("gemini/"):
        return _complete_gemini_native(
            model,
            prompt,
            image_bytes=image_bytes,
            response_format=response_format,
            temperature=temperature,
            timeout=timeout,
            num_retries=num_retries,
        )

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
        f"No provider configured for model={model!r}. Add a branch here (and its own "
        "retry/timeout handling) before routing to it."
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


# --- Streaming (chat task only) -----------------------------------------------------
#
# Deliberately additive, not a `stream: bool` flag on complete()/complete_for_task():
# changing those functions' return type would force every existing caller
# (map_pass.py, reduce_pass.py, extract_vision.py — none of which need streaming) to
# handle a str | Iterator[str] union for no benefit. These functions exist only for
# app.api.routes_chat's "/chat/stream" endpoint.
#
# Retry/fallback can only happen BEFORE the first chunk is yielded — once text has
# started streaming to a client it can't be un-sent. Each _stream_*_native generator
# therefore retries (same backoff style as its non-streaming counterpart) only the
# connect-and-validate-status phase, before its first `yield`; once real content starts
# being parsed and yielded, a failure propagates immediately instead of retrying.
#
# `timeout` here bounds each individual socket read (requests' normal streaming
# behavior), not total call duration like complete()'s blocking timeout does — a
# separate wall-clock ceiling (3x timeout) is enforced in the iteration loop so a
# pathologically slow drip can't hold a connection open indefinitely.


# A safety ceiling against a runaway reply, not the primary length control (the prompt
# itself asks for an appropriately thorough answer) — generous enough that it's rarely
# the binding constraint for a real chat answer.
DEFAULT_CHAT_MAX_OUTPUT_TOKENS = 800


def stream_chat_completion(
    prompt: str,
    *,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    num_retries: int = DEFAULT_NUM_RETRIES,
    max_output_tokens: int = DEFAULT_CHAT_MAX_OUTPUT_TOKENS,
) -> Iterator[str]:
    """Streaming entry point for the "chat" task. Tries the primary ("chat") model
    first; if it fails before yielding anything, falls back to the local Ollama model
    exactly like complete_for_task() does — but only up to that point. A failure after
    the first chunk has already been yielded propagates uncaught: the caller (the
    route's SSE generator) is expected to surface that as a visible "interrupted"
    state, not retry silently, since there's no way to undo text already sent.
    """
    primary_model = router.route("chat")
    fallback_model = router.route_fallback("chat")

    with trace_llm_call(task="chat", prompt=prompt) as trace_result:
        chunks: list[str] = []
        used_model = primary_model
        gen = _stream(
            primary_model,
            prompt,
            timeout=timeout,
            num_retries=num_retries,
            max_output_tokens=max_output_tokens,
        )
        try:
            first = next(gen, None)
        except ProviderError as exc:
            if fallback_model == primary_model:
                trace_result["error"] = str(exc)
                raise
            logger.warning(
                "llm.chat_stream_falling_back_to_local",
                primary=primary_model,
                fallback=fallback_model,
                error=str(exc),
            )
            used_model = fallback_model
            gen = _stream(
                fallback_model,
                prompt,
                timeout=timeout,
                num_retries=num_retries,
                max_output_tokens=max_output_tokens,
            )
            first = next(gen, None)

        if first is not None:
            chunks.append(first)
            yield first
        for chunk in gen:
            chunks.append(chunk)
            yield chunk

        trace_result["model"] = used_model
        trace_result["output"] = "".join(chunks)
        trace_result["fallback_used"] = used_model != primary_model


def _stream(
    model: str, prompt: str, *, timeout: int, num_retries: int, max_output_tokens: int
) -> Iterator[str]:
    """Dispatches by model prefix, same shape as complete()."""
    if model.startswith("gemini/"):
        yield from _stream_gemini_native(
            model,
            prompt,
            timeout=timeout,
            num_retries=num_retries,
            max_output_tokens=max_output_tokens,
        )
    elif model.startswith("ollama/") or model.startswith("ollama_chat/"):
        yield from _stream_ollama_native(
            model,
            prompt,
            timeout=timeout,
            num_retries=num_retries,
            max_output_tokens=max_output_tokens,
        )
    else:
        raise ProviderError(f"No streaming provider configured for model={model!r}.")


def _connect_streaming(
    *,
    build_request: Callable[[], requests.Response],
    model: str,
    num_retries: int,
) -> requests.Response:
    """Shared connect-with-retry logic for both streaming providers — isolates the one
    part of a streaming call that's still safely retryable (nothing has been yielded to
    a caller yet) from the parse-and-yield loop that isn't.
    """
    last_error: Exception | None = None
    for attempt in range(num_retries + 1):
        try:
            response = build_request()
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}")
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < num_retries:
                backoff = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "llm.stream_connect_retry",
                    model=model,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.error("llm.call_failed_after_retries", model=model, error=str(last_error))
    raise ProviderError(f"{model} unavailable after {num_retries} retries: {last_error}")


def _stream_ollama_native(
    model: str, prompt: str, *, timeout: int, num_retries: int, max_output_tokens: int
) -> Iterator[str]:
    ollama_model = model.split("/", 1)[1]
    payload: dict[str, Any] = {
        "model": ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "options": {"temperature": 0.0, "num_predict": max_output_tokens},
    }
    response = _connect_streaming(
        build_request=lambda: requests.post(
            f"{settings.ollama_base_url}/api/chat", json=payload, timeout=timeout, stream=True
        ),
        model=model,
        num_retries=num_retries,
    )

    start = time.monotonic()
    for raw_line in response.iter_lines():
        if time.monotonic() - start > timeout * 3:
            raise ProviderError(f"{model} streaming response exceeded {timeout * 3}s total")
        if not raw_line:
            continue
        chunk = json.loads(raw_line.decode("utf-8"))
        content = chunk.get("message", {}).get("content", "")
        if content:
            yield content
        if chunk.get("done"):
            break


def _stream_gemini_native(
    model: str, prompt: str, *, timeout: int, num_retries: int, max_output_tokens: int
) -> Iterator[str]:
    gemini_model = model.split("/", 1)[1]
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": max_output_tokens,
            # Confirmed by live testing against this exact endpoint (not assumed):
            # gemini-3.8-flash spends tokens on an invisible "thinking" step by
            # default, counted against maxOutputTokens — a 300-token budget produced
            # 285 thinking tokens and an 11-token, mid-sentence-truncated visible
            # answer (usageMetadata.thoughtsTokenCount). Disabling it both fixed the
            # truncation and cut a test call from ~8s to ~3.4s — thinking time was the
            # real latency cost, not generation length. Chat has no need for this
            # model's internal reasoning step; map_pass.py's own use of this same
            # model is untouched here (a deliberate, separate decision, not silently
            # bundled into a chat-latency fix).
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    url = f"{GEMINI_API_BASE}/{gemini_model}:streamGenerateContent?alt=sse"
    response = _connect_streaming(
        build_request=lambda: requests.post(
            url, json=payload, headers=headers, timeout=timeout, stream=True
        ),
        model=model,
        num_retries=num_retries,
    )

    start = time.monotonic()
    for raw_line in response.iter_lines():
        if time.monotonic() - start > timeout * 3:
            raise ProviderError(f"{model} streaming response exceeded {timeout * 3}s total")
        if not raw_line:
            continue
        line = raw_line.decode("utf-8")
        if not line.startswith("data:"):
            continue
        body = json.loads(line[len("data:") :].strip())
        candidates = body.get("candidates") or []
        if not candidates:
            block_reason = body.get("promptFeedback", {}).get("blockReason")
            raise ProviderError(f"{model} returned no candidates (blockReason={block_reason!r})")
        for part in candidates[0].get("content", {}).get("parts", []):
            text_piece = part.get("text")
            if text_piece:
                yield text_piece


def _complete_gemini_native(
    model: str,
    prompt: str,
    *,
    image_bytes: bytes | None,
    response_format: dict | None,
    temperature: float,
    timeout: int,
    num_retries: int,
) -> str:
    """Calls the Gemini API's native generateContent endpoint directly (docs/
    DECISIONS.md #76) — same reasoning as _complete_ollama_native: hand-rolled
    timeout/retry via `requests`, not an SDK, for the same "verified enforcement,
    no library-layer surprises" property hard rule 10 requires.
    """
    gemini_model = model.split("/", 1)[1]  # strip "gemini/" prefix

    parts: list[dict[str, Any]] = []
    if image_bytes is not None:
        encoded_image = base64.b64encode(image_bytes).decode("ascii")
        parts.append({"inline_data": {"mime_type": "image/png", "data": encoded_image}})
    parts.append({"text": prompt})

    generation_config: dict[str, Any] = {"temperature": temperature}
    if response_format is not None and response_format.get("type") == "json_object":
        generation_config["responseMimeType"] = "application/json"

    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation_config,
    }
    headers = {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}
    url = f"{GEMINI_API_BASE}/{gemini_model}:generateContent"

    last_error: Exception | None = None
    for attempt in range(num_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                raise requests.HTTPError(f"{response.status_code}: {response.text[:200]}")
            response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates") or []
            if not candidates:
                # A real, non-transient case: the prompt or response tripped Gemini's
                # own safety filters (promptFeedback.blockReason) — never in this
                # project's control to retry away, so this raises immediately rather
                # than burning the retry budget on a KeyError/IndexError.
                block_reason = body.get("promptFeedback", {}).get("blockReason")
                raise ProviderError(
                    f"{model} returned no candidates (blockReason={block_reason!r})"
                )
            return candidates[0]["content"]["parts"][0]["text"]
        except (requests.RequestException, KeyError) as exc:
            last_error = exc
            if attempt < num_retries:
                backoff = (2**attempt) + random.uniform(0, 1)
                logger.warning(
                    "llm.gemini_retry",
                    model=model,
                    attempt=attempt + 1,
                    backoff_seconds=round(backoff, 2),
                    error=str(exc),
                )
                time.sleep(backoff)

    logger.error("llm.call_failed_after_retries", model=model, error=str(last_error))
    raise ProviderError(f"{model} unavailable after {num_retries} retries: {last_error}")
