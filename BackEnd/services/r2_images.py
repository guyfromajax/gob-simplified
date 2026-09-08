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


def list_keys(prefix: str) -> list[str]:
    """Every object key under ``prefix`` (paginated). One list operation set at call
    time — callers cache the result. Raises on R2 error; callers that must degrade
    gracefully (e.g. the base image pool) should catch."""
    s3, bucket = _s3()
    keys: list[str] = []
    token = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        keys.extend(o["Key"] for o in resp.get("Contents", []))
        if resp.get("IsTruncated"):
            token = resp.get("NextContinuationToken")
        else:
            break
    return keys


def put(key: str, data: bytes, content_type: str = "image/png") -> None:
    s3, bucket = _s3()
    s3.put_object(Bucket=bucket, Key=key, Body=data,
                  ContentType=content_type, CacheControl=CACHE_CONTROL)


def copy(src_key: str, dest_key: str) -> bool:
    """Server-side copy within the bucket. No download, no re-upload, no egress.

    Used by the uniform archive migration: the archive object is the painted
    artifact, and the legacy players/master/<player_id>.png key is mirrored from it
    so existing read paths keep resolving while payloads are being threaded with
    uniform_key. Cheap enough to be unremarkable -- R2 does the copy internally.
    """
    s3, bucket = _s3()
    from botocore.exceptions import ClientError
    try:
        s3.copy_object(Bucket=bucket, Key=dest_key, CopySource={"Bucket": bucket, "Key": src_key})
        return True
    except ClientError:
        logger.exception("[R2] copy failed %s -> %s", src_key, dest_key)
        return False


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
