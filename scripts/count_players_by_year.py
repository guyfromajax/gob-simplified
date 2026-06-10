#!/usr/bin/env python3
"""
Read-only: count players in gob.players by class `year`
(Senior / Junior / Sophomore / Freshman, plus any other/missing values).

Run from repo root:
  PYTHONPATH=. venv/bin/python scripts/count_players_by_year.py
"""

from __future__ import annotations

import os
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
TARGET_DB = "gob"
COLLECTION = "players"
CLASS_ORDER = ["Senior", "Junior", "Sophomore", "Freshman"]


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


def main() -> int:
    client = MongoClient(_load_mongo_uri(), serverSelectionTimeoutMS=10000)
    coll = client[TARGET_DB][COLLECTION]

    total = coll.count_documents({})
    counts = {
        doc["_id"]: doc["count"]
        for doc in coll.aggregate([{"$group": {"_id": "$year", "count": {"$sum": 1}}}])
    }

    print(f"[{TARGET_DB}.{COLLECTION}] total players: {total}\n")
    shown = 0
    for year in CLASS_ORDER:
        n = counts.pop(year, 0)
        shown += n
        print(f"  {year:<10} {n}")

    # Anything not in the canonical four (None / unexpected strings) — surfaced, not hidden.
    if counts:
        print("\n  Other / missing `year` values:")
        for key, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            print(f"    {str(key):<10} {n}")
            shown += n

    print(f"\n  accounted for: {shown} / {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
