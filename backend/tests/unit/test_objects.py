import uuid

import pytest
from moto import mock_aws

from app.core.config import settings
from app.storage import objects


@pytest.fixture(autouse=True)
def _mock_friendly_client(monkeypatch):
    """get_s3_client() is lru_cache'd — must be cleared so each test gets a fresh client.
    Also clears the configured endpoint_url: moto's mock_aws only intercepts AWS's own
    default endpoints, not an arbitrary custom one (MinIO-style) — see
    app/storage/objects.py's get_s3_client for the corresponding production-side handling.
    """
    monkeypatch.setattr(settings, "s3_endpoint_url", "")
    objects.get_s3_client.cache_clear()
    yield
    objects.get_s3_client.cache_clear()


@mock_aws
def test_upload_and_read_pdf_roundtrip() -> None:
    objects.get_s3_client().create_bucket(Bucket=settings.s3_bucket)
    document_id = uuid.uuid4()

    key = objects.upload_pdf(document_id, b"%PDF-1.4 fake content")
    assert key == f"documents/{document_id}/original.pdf"

    roundtripped = objects.get_object_bytes(key)
    assert roundtripped == b"%PDF-1.4 fake content"


@mock_aws
def test_upload_page_image_key_format() -> None:
    objects.get_s3_client().create_bucket(Bucket=settings.s3_bucket)
    document_id = uuid.uuid4()

    key = objects.upload_page_image(document_id, 7, b"fake-png-bytes")
    assert key == f"documents/{document_id}/pages/00007.png"
    assert objects.get_object_bytes(key) == b"fake-png-bytes"


@mock_aws
def test_ensure_bucket_exists_is_idempotent() -> None:
    objects.ensure_bucket_exists()
    objects.ensure_bucket_exists()  # must not raise on the second call
    # bucket now exists — an upload should succeed without a separate create_bucket call
    key = objects.upload_pdf(uuid.uuid4(), b"data")
    assert objects.get_object_bytes(key) == b"data"
