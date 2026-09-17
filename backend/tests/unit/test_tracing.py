"""Unit tests for app.core.tracing — fakes the Langfuse client (module-level `_client`
swapped via monkeypatch), no real Langfuse instance needed, per CLAUDE.md hard rule 8.
"""

import pytest

from app.core import tracing


class FakeLangfuseClient:
    def __init__(self) -> None:
        self.generations: list[dict] = []
        self.flushed = False

    def generation(self, **kwargs):
        self.generations.append(kwargs)

    def flush(self):
        self.flushed = True


class RaisingLangfuseClient:
    """Simulates a real Langfuse-side failure (network error, bad host) — tracing must
    never be the reason a real pipeline call fails.
    """

    def generation(self, **kwargs):
        raise ConnectionError("langfuse host unreachable")

    def flush(self):
        raise ConnectionError("langfuse host unreachable")


@pytest.fixture
def fake_client(monkeypatch):
    client = FakeLangfuseClient()
    monkeypatch.setattr(tracing, "_client", client)
    return client


def test_no_client_configured_yields_empty_dict_and_records_nothing(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "_client", None)

    with tracing.trace_llm_call(task="map", prompt="hello") as result:
        result["model"] = "ollama_chat/gpt-oss:20b-cloud"
        result["output"] = "some output"
    # no exception, nothing to assert against — there's no client to have recorded to


def test_successful_call_records_one_generation_with_output(fake_client) -> None:
    with tracing.trace_llm_call(task="map", prompt="extract facts") as result:
        result["model"] = "ollama_chat/gpt-oss:20b-cloud"
        result["output"] = '{"dates": []}'

    assert len(fake_client.generations) == 1
    gen = fake_client.generations[0]
    assert gen["name"] == "llm.map"
    assert gen["model"] == "ollama_chat/gpt-oss:20b-cloud"
    assert gen["output"] == '{"dates": []}'
    assert gen["level"] == "DEFAULT"
    assert gen["metadata"]["task"] == "map"
    assert gen["metadata"]["fallback_used"] is False
    assert gen["metadata"]["latency_seconds"] >= 0


def test_failed_call_records_error_level_generation(fake_client) -> None:
    with tracing.trace_llm_call(task="reduce", prompt="summarize") as result:
        result["error"] = "ProviderError: unavailable after 1 retries"

    gen = fake_client.generations[0]
    assert gen["level"] == "ERROR"
    assert gen["status_message"] == "ProviderError: unavailable after 1 retries"


def test_fallback_used_is_recorded_in_metadata(fake_client) -> None:
    with tracing.trace_llm_call(task="vision", prompt="transcribe") as result:
        result["model"] = "ollama_chat/qwen2.5vl:7b"
        result["output"] = "transcribed text"
        result["fallback_used"] = True

    assert fake_client.generations[0]["metadata"]["fallback_used"] is True


def test_generation_still_recorded_even_if_the_wrapped_code_raises(fake_client) -> None:
    with pytest.raises(RuntimeError):
        with tracing.trace_llm_call(task="map", prompt="x") as result:
            result["error"] = "boom"
            raise RuntimeError("boom")

    assert len(fake_client.generations) == 1


def test_a_langfuse_side_error_never_propagates_out_of_the_context_manager(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "_client", RaisingLangfuseClient())

    with tracing.trace_llm_call(task="map", prompt="x") as result:
        result["model"] = "m"
        result["output"] = "o"
    # reaching this line means no exception escaped trace_llm_call


def test_flush_is_a_noop_when_no_client_configured(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "_client", None)

    tracing.flush()  # must not raise


def test_flush_calls_through_to_the_real_client(fake_client) -> None:
    tracing.flush()

    assert fake_client.flushed is True


def test_flush_swallows_a_langfuse_side_error(monkeypatch) -> None:
    monkeypatch.setattr(tracing, "_client", RaisingLangfuseClient())

    tracing.flush()  # must not raise
