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
    OLLAMA_LOCAL_TEXT_MODEL,
    OLLAMA_LOCAL_VISION_MODEL,
    OLLAMA_MAP_MODEL,
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
    assert model_used == OLLAMA_MAP_MODEL
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
    assert first_call_model == OLLAMA_MAP_MODEL
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
    assert gen["model"] == OLLAMA_MAP_MODEL
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
