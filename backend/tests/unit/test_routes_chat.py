"""Route-level tests for POST /chat — the tender/procurement terminology assistant.
LLM mocked per CLAUDE.md hard rule 8; no real Gemini/Ollama call, no real DB.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _overrides():
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    yield fake_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_chat_without_a_document_answers_from_general_knowledge() -> None:
    with patch("app.api.routes_chat.complete_for_task") as mock_complete:
        mock_complete.return_value = (
            "EMD stands for Earnest Money Deposit.",
            "gemini/gemini-3.1-pro-preview",
        )
        response = client.post("/chat", json={"message": "What does EMD mean?"})

    assert response.status_code == 200
    assert response.json()["reply"] == "EMD stands for Earnest Money Deposit."
    # No document_id was sent, so the prompt must never have tried to load one.
    prompt = mock_complete.call_args.args[1]
    assert "No document is currently open." in prompt


def test_chat_with_a_document_includes_its_existing_analysis_as_context() -> None:
    document_id = uuid.uuid4()
    with (
        patch("app.api.routes_chat.build_document_context") as mock_context,
        patch("app.api.routes_chat.complete_for_task") as mock_complete,
    ):
        mock_context.return_value = '[synopsis]\n{"title": "NHAI Road Widening"}'
        mock_complete.return_value = (
            "This tender is for road widening.",
            "gemini/gemini-3.1-pro-preview",
        )

        response = client.post(
            "/chat",
            json={"message": "What is this tender about?", "document_id": str(document_id)},
        )

    assert response.status_code == 200
    mock_context.assert_called_once()
    assert mock_context.call_args.args[1] == document_id
    prompt = mock_complete.call_args.args[1]
    assert "NHAI Road Widening" in prompt


def test_chat_includes_conversation_history_in_the_prompt() -> None:
    with patch("app.api.routes_chat.complete_for_task") as mock_complete:
        mock_complete.return_value = (
            "Sure, PBG is Performance Bank Guarantee.",
            "gemini/gemini-3.1-pro-preview",
        )
        response = client.post(
            "/chat",
            json={
                "message": "and PBG?",
                "history": [
                    {"role": "user", "content": "What does EMD mean?"},
                    {"role": "assistant", "content": "Earnest Money Deposit."},
                ],
            },
        )

    assert response.status_code == 200
    prompt = mock_complete.call_args.args[1]
    assert "What does EMD mean?" in prompt
    assert "Earnest Money Deposit." in prompt


def test_chat_requires_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: "test-user"
