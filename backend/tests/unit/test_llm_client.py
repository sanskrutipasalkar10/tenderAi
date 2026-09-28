"""Unit tests for app.llm.client's cloud->local fallback (docs/DECISIONS.md #32).
`complete()` itself is mocked so these tests exercise complete_for_task's fallback
logic in isolation, without touching litellm/Ollama/network — $0, deterministic,
per CLAUDE.md hard rule 8.
"""

from unittest.mock import patch

import pytest

from app.core import tracing
from app.core.exceptions import ProviderError
from app.llm.client import complete_for_task
from app.llm.router import (
    GEMINI_MAP_MODEL,
    OLLAMA_LOCAL_TEXT_MODEL,
    OLLAMA_LOCAL_VISION_MODEL,
)


class _FakeTracingClient:
    def __init__(self) -> None:
        self.generations: list[dict] = []

    def generation(self, **kwargs):
        self.generations.append(kwargs)


@pytest.fixture
def fake_tracing_client(monkeypatch):
    client = _FakeTracingClient()
    monkeypatch.setattr(tracing, "_client", client)
    return client


@patch("app.llm.client.complete")
def test_primary_success_never_touches_fallback(mock_complete) -> None:
    mock_complete.return_value = "primary response"

    text, model_used = complete_for_task("map", "some prompt")

    assert text == "primary response"
    assert model_used == GEMINI_MAP_MODEL
    mock_complete.assert_called_once()


@patch("app.llm.client.complete")
def test_primary_failure_falls_back_to_local(mock_complete) -> None:
    mock_complete.side_effect = [
        ProviderError("simulated Ollama Cloud outage"),
        "fallback response",
    ]

    text, model_used = complete_for_task("map", "some prompt")

    assert text == "fallback response"
    assert model_used == OLLAMA_LOCAL_TEXT_MODEL
    assert mock_complete.call_count == 2
    first_call_model = mock_complete.call_args_list[0].args[0]
    second_call_model = mock_complete.call_args_list[1].args[0]
    assert first_call_model == GEMINI_MAP_MODEL
    assert second_call_model == OLLAMA_LOCAL_TEXT_MODEL


@patch("app.llm.client.complete")
def test_both_primary_and_fallback_failing_raises_provider_error(mock_complete) -> None:
    mock_complete.side_effect = ProviderError("down everywhere")

    with pytest.raises(ProviderError):
        complete_for_task("vision", "some prompt", image_bytes=b"fake-png")

    assert mock_complete.call_count == 2


@patch("app.llm.client.complete")
def test_local_vision_mode_has_no_further_fallback(mock_complete, monkeypatch) -> None:
    """When settings.use_local_vision is already set, route('vision') IS the local
    model — there's nothing further to fall back to, so a failure should raise
    immediately (one call, not two).
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "use_local_vision", True)
    mock_complete.side_effect = ProviderError("local model unavailable")

    with pytest.raises(ProviderError):
        complete_for_task("vision", "some prompt", image_bytes=b"fake-png")

    mock_complete.assert_called_once()
    assert mock_complete.call_args.args[0] == OLLAMA_LOCAL_VISION_MODEL


@patch("app.llm.client.complete")
def test_successful_call_is_traced_with_the_model_actually_used(
    mock_complete, fake_tracing_client
) -> None:
    mock_complete.return_value = "primary response"

    complete_for_task("map", "some prompt")

    assert len(fake_tracing_client.generations) == 1
    gen = fake_tracing_client.generations[0]
    assert gen["name"] == "llm.map"
    assert gen["model"] == GEMINI_MAP_MODEL
    assert gen["output"] == "primary response"
    assert gen["metadata"]["fallback_used"] is False


@patch("app.llm.client.complete")
def test_fallback_call_is_traced_with_fallback_used_true(
    mock_complete, fake_tracing_client
) -> None:
    mock_complete.side_effect = [ProviderError("simulated outage"), "fallback response"]

    complete_for_task("map", "some prompt")

    gen = fake_tracing_client.generations[0]
    assert gen["model"] == OLLAMA_LOCAL_TEXT_MODEL
    assert gen["output"] == "fallback response"
    assert gen["metadata"]["fallback_used"] is True


@patch("app.llm.client.complete")
def test_total_failure_is_traced_at_error_level(mock_complete, fake_tracing_client) -> None:
    mock_complete.side_effect = ProviderError("down everywhere")

    with pytest.raises(ProviderError):
        complete_for_task("vision", "some prompt", image_bytes=b"fake-png")

    gen = fake_tracing_client.generations[0]
    assert gen["level"] == "ERROR"
    assert gen["status_message"] is not None


# --- _complete_gemini_native: real request/response shape, requests.post mocked ------


from unittest.mock import MagicMock  # noqa: E402

from app.llm.client import complete  # noqa: E402


def _fake_gemini_response(text: str) -> MagicMock:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    resp.raise_for_status = MagicMock()
    return resp


@patch("app.llm.client.requests.post")
def test_gemini_call_sends_the_api_key_header_and_strips_provider_prefix(
    mock_post, monkeypatch
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "gemini_api_key", "test-key-123")
    mock_post.return_value = _fake_gemini_response("gemini reply")

    result = complete("gemini/gemini-3.8-flash", "some prompt")

    assert result == "gemini reply"
    call = mock_post.call_args
    assert call.args[0] == (
        "https://aiplatform.googleapis.com/v1/publishers/google/models/"
        "gemini-3.8-flash:generateContent"
    )
    assert call.kwargs["headers"]["x-goog-api-key"] == "test-key-123"
    assert call.kwargs["json"]["contents"][0]["role"] == "user"
    assert call.kwargs["json"]["contents"][0]["parts"][0]["text"] == "some prompt"


@patch("app.llm.client.requests.post")
def test_gemini_call_includes_image_as_inline_data(mock_post) -> None:
    mock_post.return_value = _fake_gemini_response("described the image")

    complete("gemini/gemini-3.8-flash", "describe this", image_bytes=b"fake-png-bytes")

    parts = mock_post.call_args.kwargs["json"]["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["text"] == "describe this"


@patch("app.llm.client.requests.post")
def test_gemini_call_requests_json_mime_type_for_structured_output(mock_post) -> None:
    mock_post.return_value = _fake_gemini_response("{}")

    complete("gemini/gemini-3.8-flash", "some prompt", response_format={"type": "json_object"})

    config = mock_post.call_args.kwargs["json"]["generationConfig"]
    assert config["responseMimeType"] == "application/json"


@patch("app.llm.client.requests.post")
def test_gemini_call_raises_provider_error_on_empty_candidates_no_retry(mock_post) -> None:
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}
    resp.raise_for_status = MagicMock()
    mock_post.return_value = resp

    with pytest.raises(ProviderError, match="SAFETY"):
        complete("gemini/gemini-3.8-flash", "some prompt", num_retries=2)

    # A safety block is not transient — must not burn the retry budget on it.
    mock_post.assert_called_once()


@patch("app.llm.client.time.sleep")
@patch("app.llm.client.requests.post")
def test_gemini_call_retries_on_5xx_then_succeeds(mock_post, _mock_sleep) -> None:
    error_resp = MagicMock(status_code=503, text="Service Unavailable")
    mock_post.side_effect = [error_resp, _fake_gemini_response("recovered")]

    result = complete("gemini/gemini-3.8-flash", "some prompt", num_retries=1)

    assert result == "recovered"
    assert mock_post.call_count == 2


@patch("app.llm.client.time.sleep")
@patch("app.llm.client.requests.post")
def test_gemini_call_raises_provider_error_after_retries_exhausted(mock_post, _mock_sleep) -> None:
    error_resp = MagicMock(status_code=500, text="down")
    mock_post.return_value = error_resp

    with pytest.raises(ProviderError, match="gemini/gemini-3.8-flash"):
        complete("gemini/gemini-3.8-flash", "some prompt", num_retries=1)

    assert mock_post.call_count == 2
