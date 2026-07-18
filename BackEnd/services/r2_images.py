"""
Thin Cloudflare R2 client for the recruit paint service (read kits, write masters).

Credentials come from env vars (wired on Railway), mirroring the offline
uploader's names: R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET.
The client is created lazily so importing this module never requires creds; call
is_configured() to check before use and degrade gracefully when unset.
"""
import os
import logging

logger = logging.getLogger(__name__)

_REQUIRED = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")
CACHE_CONTROL = "public, max-age=86400"

_state = {}


def is_configured() -> bool:
    return all(os.environ.get(k) for k in _REQUIRED)


def _s3():
    if "client" not in _state:
        import boto3
        _state["client"] = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )
        _state["bucket"] = os.environ["R2_BUCKET"]
    return _state["client"], _state["bucket"]


def exists(key: str) -> bool:
    s3, bucket = _s3()
    from botocore.exceptions import ClientError
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise


def get(key: str) -> bytes:
    s3, bucket = _s3()
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def put(key: str, data: bytes, content_type: str = "image/png") -> None:
    s3, bucket = _s3()
    s3.put_object(Bucket=bucket, Key=key, Body=data,
                  ContentType=content_type, CacheControl=CACHE_CONTROL)


def delete(key: str) -> bool:
    """Delete an object. Returns True if the object existed and was removed, False
    if it was already absent. Idempotent — deleting a missing key is not an error."""
    s3, bucket = _s3()
    from botocore.exceptions import ClientError
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return False
        raise
    s3.delete_object(Bucket=bucket, Key=key)
    return True
