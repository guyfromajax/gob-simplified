#!/usr/bin/env python3
"""
Replace gob.fcp_skeletons and gob.hct_skeletons with data from gob-staging.

Usage:
  .venv/bin/python scripts/replace_gob_fcp_hct_from_staging.py --dry-run
  .venv/bin/python scripts/replace_gob_fcp_hct_from_staging.py --apply
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def load_mongo_uri() -> str:
    load_env_file(ROOT / ".env.local")
    load_env_file(ROOT / ".env")
    uri = os.environ.get("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI not found in environment/.env files")
    return uri


def pull_docs(coll) -> list[dict[str, Any]]:
    docs = []
    for doc in coll.find({}):
        d = dict(doc)
        d.pop("_id", None)
        docs.append(d)
    return docs


def replace_collection(dest_coll, src_docs: list[dict[str, Any]]) -> tuple[int, int]:
    # Full replace as requested.
    deleted = dest_coll.delete_many({}).deleted_count
    inserted = 0
    if src_docs:
        inserted = len(dest_coll.insert_many(src_docs).inserted_ids)
    return deleted, inserted


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace gob FCP/HCT skeleton collections with gob-staging versions."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Show counts only, no writes.")
    mode.add_argument("--apply", action="store_true", help="Perform replacement.")
    args = parser.parse_args()

    uri = load_mongo_uri()
    client = MongoClient(uri, serverSelectionTimeoutMS=10000)

    src_db = client["gob-staging"]
    dst_db = client["gob"]

    mappings = [
        ("fcp_skeletons", src_db["fcp_skeletons"], dst_db["fcp_skeletons"]),
        ("hct_skeletons", src_db["hct_skeletons"], dst_db["hct_skeletons"]),
    ]

    for name, src_coll, dst_coll in mappings:
        src_docs = pull_docs(src_coll)
        dst_count_before = dst_coll.count_documents({})
        print(
            f"[plan] {name}: gob-staging has {len(src_docs)} doc(s), gob currently has {dst_count_before} doc(s)"
        )
        if args.apply:
            deleted, inserted = replace_collection(dst_coll, src_docs)
            dst_count_after = dst_coll.count_documents({})
            print(
                f"[apply] {name}: deleted={deleted}, inserted={inserted}, gob now has {dst_count_after} doc(s)"
            )
        else:
            print(f"[dry-run] {name}: no changes made")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

