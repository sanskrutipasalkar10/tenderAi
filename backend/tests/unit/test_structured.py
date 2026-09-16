"""Unit tests for app.llm.structured — LLM call mocked at complete_for_task (the
boundary structured.py itself calls), per CLAUDE.md hard rule 8.
"""

import json
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from app.core.exceptions import ProviderError
from app.llm.structured import complete_structured


class _SimpleSchema(BaseModel):
    value: str


@patch("app.llm.structured.complete_for_task")
def test_valid_json_on_first_try(mock_complete_for_task) -> None:
    mock_complete_for_task.return_value = (
        json.dumps({"value": "hello"}),
        "ollama_chat/gpt-oss:20b-cloud",
    )

    result, model_used = complete_structured("map", "prompt", _SimpleSchema)

    assert result.value == "hello"
    assert model_used == "ollama_chat/gpt-oss:20b-cloud"
    mock_complete_for_task.assert_called_once()


@patch("app.llm.structured.complete_for_task")
def test_json_wrapped_in_prose_is_extracted(mock_complete_for_task) -> None:
    mock_complete_for_task.return_value = (
        'Sure, here is the JSON:\n{"value": "extracted"}\nHope that helps!',
        "ollama_chat/gpt-oss:20b-cloud",
    )

    result, _ = complete_structured("map", "prompt", _SimpleSchema)

    assert result.value == "extracted"


@patch("app.llm.structured.complete_for_task")
def test_retries_on_invalid_json_then_succeeds(mock_complete_for_task) -> None:
    mock_complete_for_task.side_effect = [
        ("not json at all", "ollama_chat/gpt-oss:20b-cloud"),
        (json.dumps({"value": "second try"}), "ollama_chat/gpt-oss:20b-cloud"),
    ]

    result, _ = complete_structured("map", "prompt", _SimpleSchema, max_parse_retries=2)

    assert result.value == "second try"
    assert mock_complete_for_task.call_count == 2


@patch("app.llm.structured.complete_for_task")
def test_retries_on_schema_mismatch(mock_complete_for_task) -> None:
    mock_complete_for_task.side_effect = [
        (json.dumps({"wrong_field": "x"}), "ollama_chat/gpt-oss:20b-cloud"),
        (json.dumps({"value": "correct"}), "ollama_chat/gpt-oss:20b-cloud"),
    ]

    result, _ = complete_structured("map", "prompt", _SimpleSchema, max_parse_retries=2)

    assert result.value == "correct"


@patch("app.llm.structured.complete_for_task")
def test_exhausting_retries_raises_provider_error(mock_complete_for_task) -> None:
    mock_complete_for_task.return_value = ("garbage, not json", "ollama_chat/gpt-oss:20b-cloud")

    with pytest.raises(ProviderError):
        complete_structured("map", "prompt", _SimpleSchema, max_parse_retries=1)

    assert mock_complete_for_task.call_count == 2  # initial + 1 retry


@patch("app.llm.structured.complete_for_task")
def test_underlying_provider_failure_propagates(mock_complete_for_task) -> None:
    mock_complete_for_task.side_effect = ProviderError("cloud and local both down")

    with pytest.raises(ProviderError):
        complete_structured("map", "prompt", _SimpleSchema)
