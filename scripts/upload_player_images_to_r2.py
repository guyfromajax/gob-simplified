#!/usr/bin/env python3
"""
Upload player images to Cloudflare R2 (bucket: gob-player-images).

Reads credentials from process variables or external ``~/.config/gob/r2.env``.
Uploads <source>/*.png  ->  R2 key players/master/<filename>

Default source is the gitignored staging dir assets_staging/players/ so new bulk
images never enter the repo. Override with --source.

Idempotent: skips any object already present in R2 whose stored sha256 metadata
matches the local file, so re-running only uploads new/changed images. This is
the intended workflow for adding new player images over time.

Writes an audit manifest to scripts/r2_upload_manifest.csv.

Usage:
    ./venv/bin/python3 scripts/upload_player_images_to_r2.py --dry-run            # preview (staging dir)
    ./venv/bin/python3 scripts/upload_player_images_to_r2.py                      # upload staging dir
    ./venv/bin/python3 scripts/upload_player_images_to_r2.py --source <dir>       # upload from <dir>
"""
import argparse
import csv
import hashlib
import os
import sys

import boto3
from botocore.exceptions import ClientError
from script_secrets import ScriptSecretError, load_r2_credentials

# ---- Tunable constants ------------------------------------------------------
# Default source: a gitignored staging dir so new bulk images never enter the repo.
# Override with --source (e.g. the legacy FrontEnd dir during initial migration).
DEFAULT_SOURCE    = "assets_staging/players"
KEY_PREFIX        = "players/master/"      # R2 object key prefix for canonical masters
CONTENT_TYPE  = "image/png"
CACHE_CONTROL = "public, max-age=86400"     # 1 day at origin; CDN/transform layer caches longer
MANIFEST_PATH = "scripts/r2_upload_manifest.csv"
# ----------------------------------------------------------------------------


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_sha256(s3, bucket, key):
    """Return stored sha256 metadata for an existing object, or None if absent."""
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
        return head.get("Metadata", {}).get("sha256")
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            return None
        raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="preview without uploading")
    ap.add_argument("--source", default=DEFAULT_SOURCE,
                    help=f"directory of <uuid>.png files to upload (default: {DEFAULT_SOURCE})")
    args = ap.parse_args()
    source_dir = args.source

    try:
        env = load_r2_credentials()
    except ScriptSecretError as exc:
        sys.exit(f"ERROR: {exc}")
    s3 = boto3.client(
        "s3",
        endpoint_url=env["R2_ENDPOINT"],
        aws_access_key_id=env["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    bucket = env["R2_BUCKET"]

    if not os.path.isdir(source_dir):
        sys.exit(f"Source dir not found: {source_dir}  (create it or pass --source <dir>)")
    files = sorted(f for f in os.listdir(source_dir) if f.lower().endswith(".png"))
    if not files:
        sys.exit(f"No .png files found in {source_dir}")

    mode = "DRY RUN — nothing will be uploaded" if args.dry_run else "UPLOADING"
    print(f"[{mode}] {len(files)} local PNG(s) from {source_dir} -> s3://{bucket}/{KEY_PREFIX}\n")

    rows = []
    uploaded = skipped = failed = 0
    for i, fname in enumerate(files, 1):
        local_path = os.path.join(source_dir, fname)
        key = KEY_PREFIX + fname
        size = os.path.getsize(local_path)
        digest = sha256_of(local_path)
        status = ""
        try:
            if remote_sha256(s3, bucket, key) == digest:
                status = "skipped (unchanged)"
                skipped += 1
            elif args.dry_run:
                status = "would upload"
            else:
                s3.upload_file(
                    local_path, bucket, key,
                    ExtraArgs={
                        "ContentType": CONTENT_TYPE,
                        "CacheControl": CACHE_CONTROL,
                        "Metadata": {"sha256": digest},
                    },
                )
                status = "uploaded"
                uploaded += 1
        except Exception as e:  # noqa: BLE001
            status = f"FAILED: {e}"
            failed += 1

        print(f"  [{i:>4}/{len(files)}] {fname:<42} {size:>9,} B  {status}")
        rows.append({
            "filename": fname,
            "asset_key": key,
            "remote_url": f"https://assets.geekedoutgames.com/{key}",
            "file_size": size,
            "sha256": digest,
            "status": status,
        })

    with open(MANIFEST_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"\nSummary: {uploaded} uploaded, {skipped} skipped, {failed} failed, "
          f"{len(files)} total")
    print(f"Manifest written to {MANIFEST_PATH}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
