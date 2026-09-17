"""CORS is easy to get right in code and silently wrong in practice — a missing
origin doesn't raise a server-side error, it just makes the browser block every
request with no signal the backend ever sees (found for real driving the frontend in
a real browser, docs/DECISIONS.md #56). This test would have caught that gap directly.
"""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)


def test_configured_frontend_origin_is_allowed() -> None:
    response = client.options(
        "/documents",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_an_unlisted_origin_is_not_allowed() -> None:
    response = client.options(
        "/documents",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette's CORS middleware still returns 200 for the preflight itself, but
    # omits the allow-origin header for a disallowed origin — that's what actually
    # makes the browser block the real request.
    assert "access-control-allow-origin" not in response.headers


def test_cors_allowed_origins_list_parses_the_comma_separated_setting(monkeypatch) -> None:
    monkeypatch.setattr(
        settings, "cors_allowed_origins", "http://localhost:3000, http://localhost:3002"
    )
    assert settings.cors_allowed_origins_list == [
        "http://localhost:3000",
        "http://localhost:3002",
    ]
