#!/usr/bin/env python3
"""
Export unused alpha OTP codes from gob-staging.alpha_otps to a projects doc.

Queries documents with used: false and writes otp_code values to:
  _documentation_master/projects/staging_otps.md

Run from repo root:
  PYTHONPATH=. venv/bin/python scripts/export_staging_unused_otps.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
TARGET_DB = "gob-staging"
COLLECTION = "alpha_otps"
OUTPUT_PATH = ROOT / "_documentation_master" / "projects" / "staging_otps.md"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _load_mongo_uri() -> str:
    _load_env_file(ROOT / ".env.local")
    _load_env_file(ROOT / ".env")
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment/.env files")
    return uri


def fetch_unused_otp_codes(client: MongoClient) -> list[str]:
    collection = client[TARGET_DB][COLLECTION]
    cursor = collection.find(
        {"used": False},
        {"otp_code": 1, "_id": 0},
    ).sort("otp_code", 1)
    codes: list[str] = []
    for doc in cursor:
        code = doc.get("otp_code")
        if isinstance(code, str) and code.strip():
            codes.append(code.strip())
    return codes


def write_output(codes: list[str]) -> None:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Unused staging OTPs ({len(codes)})",
        "",
        f"Source: `{TARGET_DB}.{COLLECTION}` where `used: false`",
        "",
        f"Generated: {generated_at}",
        "",
    ]
    lines.extend(codes)
    lines.append("")
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    uri = _load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    codes = fetch_unused_otp_codes(client)
    write_output(codes)
    print(f"[{TARGET_DB}.{COLLECTION}] unused OTPs: {len(codes)}")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
