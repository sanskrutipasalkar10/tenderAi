"""Unit tests for the ingestion orchestrator (app/services/ingestion.py).

The DB session is mocked (no real Postgres available yet — colleague's instance is
pending, per docs/DECISIONS.md). S3 is real-but-mocked via moto, with genuine fixture PDF
bytes round-tripped through it, so classify.py/extract_native.py run against real
content — only persistence is faked. This is the honest boundary given the environment:
extraction correctness is verified for real; DB write correctness is verified by
inspecting what would have been written, not by an actual round-trip.
"""

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from moto import mock_aws

from app.core.config import settings
from app.models.document import Document
from app.models.extracted_table import ExtractedTable
from app.models.page import Page
from app.services import ingestion
from app.storage import objects

FIXTURES_DIR = Path(__file__).parent.parent.parent / "evals" / "fixtures" / "pdfs"


@pytest.fixture(autouse=True)
def _mock_friendly_s3(monkeypatch):
    monkeypatch.setattr(settings, "s3_endpoint_url", "")
    objects.get_s3_client.cache_clear()
    yield
    objects.get_s3_client.cache_clear()


class FakeSession:
    """Records added rows and assigns IDs on add(), mimicking what a real flush would
    do for Page.id, without needing an actual Postgres round-trip.
    """

    def __init__(self, document: Document) -> None:
        self._document = document
        self.added: list = []
        self.commit_count = 0

    def get(self, model, pk):
        if model is Document and pk == self._document.id:
            return self._document
        return None

    def add(self, obj) -> None:
        if isinstance(obj, Page) and obj.id is None:
            obj.id = uuid.uuid4()
        self.added.append(obj)

    def flush(self) -> None:
        pass

    def commit(self) -> None:
        self.commit_count += 1

    def refresh(self, obj) -> None:
        pass


@mock_aws
@patch("app.pipeline.extract_vision.complete")
def test_run_ingestion_processes_every_page_and_sets_status(mock_complete) -> None:
    # Vision extraction (page 5, scanned) is mocked per CLAUDE.md hard rule 8 — a unit
    # test must cost $0, be deterministic, and not depend on Ollama being reachable
    # (it isn't, in CI). Real vision-call correctness is covered by
    # evals/test_extraction_completeness.py and manual validation against Ollama
    # Cloud, not here.
    mock_complete.return_value = "Mocked signature page transcription."

    objects.get_s3_client().create_bucket(Bucket=settings.s3_bucket)
    pdf_bytes = (FIXTURES_DIR / "fixture_01_nhai_road.pdf").read_bytes()

    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        filename="fixture_01_nhai_road.pdf",
        status="uploaded",
        original_pdf_s3_key=objects.upload_pdf(document_id, pdf_bytes),
    )
    db = FakeSession(document)

    result = ingestion.run_ingestion(db, document_id)

    assert result.status == "extracted"
    assert result.total_pages == 6  # fixture_01 has 6 pages, per golden_pages.jsonl

    page_rows = [row for row in db.added if isinstance(row, Page)]
    assert len(page_rows) == 6, "every page must produce a Page row (zero-page-drop)"
    assert {p.page_number for p in page_rows} == set(range(6))

    # page 4 is the BOQ table — must have produced an ExtractedTable row too
    table_rows = [row for row in db.added if isinstance(row, ExtractedTable)]
    assert len(table_rows) == 1
    assert table_rows[0].table_data["headers"][0] == "Item No."

    # page 5 is scanned — now vision-extracted (mocked), not a placeholder
    scanned_page = next(p for p in page_rows if p.page_number == 5)
    assert scanned_page.classification == "scanned_image"
    assert scanned_page.raw_text == "Mocked signature page transcription."
    assert scanned_page.extraction_method == "vision_cloud"
    mock_complete.assert_called_once()


@mock_aws
def test_run_ingestion_raises_for_missing_document() -> None:
    document = Document(id=uuid.uuid4(), filename="x", status="uploaded")
    db = FakeSession(document)

    with pytest.raises(ValueError, match="not found"):
        ingestion.run_ingestion(db, uuid.uuid4())


@mock_aws
def test_run_ingestion_raises_when_no_pdf_uploaded() -> None:
    document_id = uuid.uuid4()
    document = Document(
        id=document_id, filename="x", status="uploaded", original_pdf_s3_key=None
    )
    db = FakeSession(document)

    with pytest.raises(ValueError, match="no uploaded PDF"):
        ingestion.run_ingestion(db, document_id)
