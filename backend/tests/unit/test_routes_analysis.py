"""Route-level tests for document_analysis — serving (GET, existing) and the human
review endpoint (PATCH .../go_no_go/review, new). LLM/DB mocked per CLAUDE.md hard
rule 8.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.document_analysis import DocumentAnalysis

client = TestClient(app)


@pytest.fixture(autouse=True)
def _overrides():
    fake_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: fake_db
    app.dependency_overrides[get_current_user] = lambda: "test-user"
    yield fake_db
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


def _analysis(result: dict, document_id: uuid.UUID | None = None) -> DocumentAnalysis:
    now = datetime.now(timezone.utc)
    return DocumentAnalysis(
        id=uuid.uuid4(),
        document_id=document_id or uuid.uuid4(),
        module="go_no_go",
        result=result,
        model_used="ollama_chat/gpt-oss:120b-cloud",
        created_at=now,
    )


def test_get_document_analysis_404s_when_not_yet_analyzed(_overrides) -> None:
    _overrides.query.return_value.filter.return_value.first.return_value = None

    response = client.get(f"/documents/{uuid.uuid4()}/analysis/go_no_go")

    assert response.status_code == 404


def test_get_document_analysis_returns_the_stored_result(_overrides) -> None:
    analysis = _analysis({"score": 90, "decision": "Go", "criteria_matches": [],
                           "gaps": [], "next_steps": [], "factor_scores": None})
    _overrides.query.return_value.filter.return_value.first.return_value = analysis

    response = client.get(f"/documents/{analysis.document_id}/analysis/go_no_go")

    assert response.status_code == 200
    assert response.json()["result"]["decision"] == "Go"


def test_review_404s_when_no_go_no_go_analysis_exists(_overrides) -> None:
    _overrides.query.return_value.filter.return_value.first.return_value = None

    response = client.patch(
        f"/documents/{uuid.uuid4()}/analysis/go_no_go/review",
        json={"overrides": [{"criterion_index": 0, "status": "pass", "note": None}]},
    )

    assert response.status_code == 404


def test_review_applies_override_and_returns_updated_decision(_overrides) -> None:
    from app.pipeline import reduce_pass

    all_high = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 90)
    analysis = _analysis({
        "score": 0,
        "decision": "No-Go",
        "criteria_matches": [
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "No relevant information in company profile",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": "Mandatory certification unavailable",
                "criterion_type": "eligibility",
                "human_override": None,
            }
        ],
        "gaps": ["Mandatory certification unavailable"],
        "next_steps": [],
        "factor_scores": all_high,
    })
    _overrides.query.return_value.filter.return_value.first.return_value = analysis

    response = client.patch(
        f"/documents/{analysis.document_id}/analysis/go_no_go/review",
        json={
            "overrides": [
                {"criterion_index": 0, "status": "pass", "note": "Certificate on file"}
            ]
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["decision"] == "Go"
    assert body["result"]["gaps"] == []
    assert body["result"]["criteria_matches"][0]["human_override"]["status"] == "pass"
    _overrides.commit.assert_called_once()


def test_review_pass_override_sends_notification_email(_overrides) -> None:
    from app.pipeline import reduce_pass

    all_high = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 90)
    analysis = _analysis({
        "score": 0,
        "decision": "No-Go",
        "criteria_matches": [
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "No relevant information in company profile",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": "Mandatory certification unavailable",
                "criterion_type": "eligibility",
                "human_override": None,
            }
        ],
        "gaps": ["Mandatory certification unavailable"],
        "next_steps": [],
        "factor_scores": all_high,
    })
    _overrides.query.return_value.filter.return_value.first.return_value = analysis

    with patch("app.api.routes_analysis.send_review_notification") as mock_send:
        response = client.patch(
            f"/documents/{analysis.document_id}/analysis/go_no_go/review",
            json={
                "overrides": [
                    {"criterion_index": 0, "status": "pass", "note": "Certificate on file"}
                ]
            },
        )

    assert response.status_code == 200
    mock_send.assert_called_once_with(
        document_id=str(analysis.document_id),
        criterion="Mandatory ISO 9001 certification",
        required="ISO 9001:2015",
        company_value="No relevant information in company profile",
        reviewer_note="Certificate on file",
    )


def test_review_fail_override_does_not_send_notification_email(_overrides) -> None:
    from app.pipeline import reduce_pass

    all_high = dict.fromkeys(reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 90)
    analysis = _analysis({
        "score": 0,
        "decision": "No-Go",
        "criteria_matches": [
            {
                "criterion": "Mandatory ISO 9001 certification",
                "required": "ISO 9001:2015",
                "company_value": "Certificate expired in 2023",
                "status": "insufficient_data",
                "page_ref": 2,
                "gate": "Mandatory certification unavailable",
                "criterion_type": "eligibility",
                "human_override": None,
            }
        ],
        "gaps": ["Mandatory certification unavailable"],
        "next_steps": [],
        "factor_scores": all_high,
    })
    _overrides.query.return_value.filter.return_value.first.return_value = analysis

    with patch("app.api.routes_analysis.send_review_notification") as mock_send:
        response = client.patch(
            f"/documents/{analysis.document_id}/analysis/go_no_go/review",
            json={"overrides": [{"criterion_index": 0, "status": "fail", "note": None}]},
        )

    assert response.status_code == 200
    mock_send.assert_not_called()


def test_review_out_of_range_index_returns_422(_overrides) -> None:
    analysis = _analysis({
        "score": 90, "decision": "Go", "criteria_matches": [], "gaps": [],
        "next_steps": [], "factor_scores": None,
    })
    _overrides.query.return_value.filter.return_value.first.return_value = analysis

    response = client.patch(
        f"/documents/{analysis.document_id}/analysis/go_no_go/review",
        json={"overrides": [{"criterion_index": 5, "status": "pass", "note": None}]},
    )

    assert response.status_code == 422


def test_review_requires_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.patch(
            f"/documents/{uuid.uuid4()}/analysis/go_no_go/review",
            json={"overrides": [{"criterion_index": 0, "status": "pass", "note": None}]},
        )
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: "test-user"


def test_resubmit_404s_when_document_not_found(_overrides) -> None:
    _overrides.get.return_value = None

    response = client.post(f"/documents/{uuid.uuid4()}/analysis/go_no_go/resubmit")

    assert response.status_code == 404


def test_resubmit_calls_rescore_go_no_go_and_returns_the_updated_analysis(
    _overrides, monkeypatch
) -> None:
    from app.models.document import Document
    from app.pipeline import reduce_pass

    document_id = uuid.uuid4()
    document = Document(id=document_id, filename="t.pdf", status="ready", company_profile_id=None)
    _overrides.get.return_value = document

    updated_analysis = _analysis(
        {"score": 82, "decision": "Go", "criteria_matches": [], "gaps": [],
         "next_steps": [], "factor_scores": dict.fromkeys(
             reduce_pass.BID_DECISION_FACTOR_WEIGHTS, 82)},
        document_id,
    )
    monkeypatch.setattr(
        reduce_pass, "rescore_go_no_go", lambda db, doc, profile: updated_analysis
    )

    response = client.post(f"/documents/{document_id}/analysis/go_no_go/resubmit")

    assert response.status_code == 200
    assert response.json()["result"]["score"] == 82
    assert response.json()["result"]["decision"] == "Go"


def test_resubmit_422s_when_analysis_has_no_factor_scores_to_rescore(
    _overrides, monkeypatch
) -> None:
    from app.core.exceptions import DataQualityError
    from app.models.document import Document
    from app.pipeline import reduce_pass

    document_id = uuid.uuid4()
    document = Document(id=document_id, filename="t.pdf", status="ready", company_profile_id=None)
    _overrides.get.return_value = document

    def _raise(db, doc, profile):
        raise DataQualityError("This document's go_no_go analysis has no factor_scores")

    monkeypatch.setattr(reduce_pass, "rescore_go_no_go", _raise)

    response = client.post(f"/documents/{document_id}/analysis/go_no_go/resubmit")

    assert response.status_code == 422


def test_resubmit_requires_auth() -> None:
    app.dependency_overrides.pop(get_current_user, None)
    try:
        response = client.post(f"/documents/{uuid.uuid4()}/analysis/go_no_go/resubmit")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[get_current_user] = lambda: "test-user"
