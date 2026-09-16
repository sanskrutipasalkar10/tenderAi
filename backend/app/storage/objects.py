"""S3-compatible object storage client — MinIO locally, S3/R2 in prod, same API either
way (docs/DECISIONS.md #11). Only pointers (`documents.original_pdf_s3_key`,
`pages.image_s3_key`) live in Postgres; the binaries live here.
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
            signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}
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
