#!/usr/bin/env python3
"""
Export unused alpha OTP codes from gob-staging.alpha_otps to a projects doc.

Queries documents with used: false and writes otp_code values to:
  _documentation_master/projects/staging_otps.md

Run from repo root:
  PYTHONPATH=. venv/bin/python scripts/export_staging_unused_otps.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

TARGET_DB = "gob-staging"
COLLECTION = "alpha_otps"
OUTPUT_PATH = ROOT / "_documentation_master" / "projects" / "staging_otps.md"


def fetch_unused_otp_codes(db) -> list[str]:
    collection = db[COLLECTION]
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=[TARGET_DB])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    codes = fetch_unused_otp_codes(connection.database)
    connection.close()
    write_output(codes)
    print(f"[{TARGET_DB}.{COLLECTION}] unused OTPs: {len(codes)}")
    print(f"Wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
