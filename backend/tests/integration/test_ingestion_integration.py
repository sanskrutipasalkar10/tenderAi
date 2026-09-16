"""Real-Postgres integration test for the ingestion pipeline — closes the gap noted in
docs/DECISIONS.md #19 (unit tests fake the DB session; this one uses a real database
connection and a real SQLAlchemy Session).

Requires DATABASE_URL in the environment/.env to point at a real, reachable Postgres
with migrations applied (`alembic upgrade head`). Skipped automatically if no database
is reachable, so `pytest tests/unit` (which never needs this) and CI (which has no
Postgres configured yet) aren't affected — this file lives under tests/integration/ and
is not part of the CI job's `pytest tests/unit` step.

S3 is still mocked via moto (MinIO isn't set up yet) — this test specifically closes the
DB gap, not the object-storage one. Every row it writes is cleaned up at the end
(ON DELETE CASCADE from `documents` handles pages/extracted_tables) — this runs against
a real, shared team database, not a throwaway one.
"""

from pathlib import Path

import pytest
from moto import mock_aws
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.document import Document
from app.models.page import Page
from app.services import ingestion
from app.storage import objects

FIXTURES_DIR = Path(__file__).parent.parent.parent / "evals" / "fixtures" / "pdfs"


def _database_reachable() -> bool:
    try:
        engine = create_engine(settings.database_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _database_reachable(), reason="No reachable Postgres configured (DATABASE_URL)"
)


@pytest.fixture
def real_db_session():
    engine = create_engine(settings.database_url)
    session_local = sessionmaker(bind=engine)
    session = session_local()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _mock_friendly_s3(monkeypatch):
    monkeypatch.setattr(settings, "s3_endpoint_url", "")
    objects.get_s3_client.cache_clear()
    yield
    objects.get_s3_client.cache_clear()


@mock_aws
def test_run_ingestion_against_real_postgres(real_db_session) -> None:
    objects.get_s3_client().create_bucket(Bucket=settings.s3_bucket)
    pdf_bytes = (FIXTURES_DIR / "fixture_01_nhai_road.pdf").read_bytes()

    document = Document(
        filename="integration-test-fixture_01_nhai_road.pdf",
        status="uploaded",
    )
    real_db_session.add(document)
    real_db_session.commit()
    real_db_session.refresh(document)

    document.original_pdf_s3_key = objects.upload_pdf(document.id, pdf_bytes)
    real_db_session.commit()

    try:
        result = ingestion.run_ingestion(real_db_session, document.id)

        assert result.status == "extracted"
        assert result.total_pages == 6

        pages = (
            real_db_session.query(Page)
            .filter(Page.document_id == document.id)
            .order_by(Page.page_number)
            .all()
        )
        assert len(pages) == 6, "zero-page-drop invariant against a REAL database"
        assert {p.page_number for p in pages} == set(range(6))

        cover_page = pages[0]
        assert cover_page.classification == "native_text"
        assert cover_page.raw_text is not None
        assert "NOTICE INVITING TENDER" in cover_page.raw_text
        assert cover_page.content_hash is not None

        table_page = pages[4]
        assert table_page.classification == "table"

        scanned_page = pages[5]
        assert scanned_page.classification == "scanned_image"
        assert scanned_page.raw_text is None
    finally:
        # Real, shared database — clean up what this test wrote. ON DELETE CASCADE
        # (migration 0001) removes pages/extracted_tables for this document.
        real_db_session.delete(document)
        real_db_session.commit()


def test_cleanup_left_no_trace(real_db_session) -> None:
    """Runs after the test above (pytest runs a module's tests in declaration order) as
    a sanity check that cleanup actually worked, not just that it didn't raise.
    """
    count = (
        real_db_session.query(Document)
        .filter(Document.filename.like("integration-test-%"))
        .count()
    )
    assert count == 0, "integration test documents were not cleaned up"
