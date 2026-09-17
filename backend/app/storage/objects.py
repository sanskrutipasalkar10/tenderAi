"""S3-compatible object storage client — MinIO locally, S3/R2 in prod, same API either
way (docs/DECISIONS.md #11). Only pointers (`documents.original_pdf_s3_key`,
`pages.image_s3_key`) live in Postgres; the binaries live here.

Explicit connect/read timeouts (docs/DECISIONS.md #47) — botocore's `retries={"mode":
"standard"}` already gives exponential backoff+jitter and a 429-equivalent
(503 SlowDown) path, but without an explicit timeout it falls back to botocore's own
default, never verified against this project's real payload sizes (hard rule 10:
every external call needs an explicit timeout, not an inherited default).
"""

import uuid
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError

from app.core.config import settings


@lru_cache(maxsize=1)
def get_s3_client():
    # endpoint_url is omitted when unset so moto's mock_aws (which only intercepts
    # AWS's own default endpoints, not arbitrary custom ones) can patch this client in
    # tests — see tests/unit/test_objects.py. Real runs always set it (MinIO locally,
    # S3/R2 in prod) via .env.
    kwargs = {}
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=BotoConfig(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},  # botocore's own backoff+jitter
            connect_timeout=10,
            read_timeout=60,  # a 500-page PDF upload/download is the slow case here
        ),
        **kwargs,
    )


def ensure_bucket_exists() -> None:
    client = get_s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)


def upload_pdf(document_id: uuid.UUID, pdf_bytes: bytes) -> str:
    key = f"documents/{document_id}/original.pdf"
    get_s3_client().put_object(
        Bucket=settings.s3_bucket, Key=key, Body=pdf_bytes, ContentType="application/pdf"
    )
    return key


def upload_page_image(document_id: uuid.UUID, page_number: int, image_bytes: bytes) -> str:
    key = f"documents/{document_id}/pages/{page_number:05d}.png"
    get_s3_client().put_object(
        Bucket=settings.s3_bucket, Key=key, Body=image_bytes, ContentType="image/png"
    )
    return key


def get_object_bytes(key: str) -> bytes:
    response = get_s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    return response["Body"].read()
