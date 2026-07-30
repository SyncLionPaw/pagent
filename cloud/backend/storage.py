from __future__ import annotations

from functools import lru_cache

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from . import settings


@lru_cache(maxsize=1)
def s3_client() -> BaseClient:
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
    )


def ensure_bucket() -> None:
    client = s3_client()
    bucket = settings.S3_BUCKET
    try:
        client.head_bucket(Bucket=bucket)
        return
    except ClientError:
        pass
    # MinIO / path-style local S3: create without LocationConstraint for us-east-1
    client.create_bucket(Bucket=bucket)


def ping() -> dict:
    try:
        ensure_bucket()
        client = s3_client()
        client.list_objects_v2(Bucket=settings.S3_BUCKET, MaxKeys=1)
        return {"ok": True, "bucket": settings.S3_BUCKET}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def put_bytes(key: str, body: bytes, content_type: str | None = None) -> str:
    ensure_bucket()
    extra = {}
    if content_type:
        extra["ContentType"] = content_type
    s3_client().put_object(Bucket=settings.S3_BUCKET, Key=key, Body=body, **extra)
    return key


def get_bytes(key: str) -> bytes:
    response = s3_client().get_object(Bucket=settings.S3_BUCKET, Key=key)
    return response["Body"].read()


def delete_object(key: str) -> None:
    s3_client().delete_object(Bucket=settings.S3_BUCKET, Key=key)
