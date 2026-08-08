#!/usr/bin/env python3
"""Read-only year breakdown for gob-staging.players.

The script performs only ``find`` and ``count_documents`` operations. It never
writes, updates, deletes, creates indexes, or changes collection metadata.
"""

from __future__ import annotations

import os
import sys
from collections import Counter
from pathlib import Path

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
DB_NAME = "gob-staging"
COLLECTION_NAME = "players"

CANONICAL_YEARS = ("senior", "junior", "sophomore", "freshman")
YEAR_ALIASES = {
    "senior": "senior",
    "sr": "senior",
    "junior": "junior",
    "jr": "junior",
    "sophomore": "sophomore",
    "soph": "sophomore",
    "so": "sophomore",
    "freshman": "freshman",
    "fresh": "freshman",
    "fr": "freshman",
}


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _normalize_year(value: object) -> str:
    if value is None:
        return "<missing>"
    normalized = str(value).strip().lower().replace(".", "")
    if not normalized:
        return "<missing>"
    return YEAR_ALIASES.get(normalized, f"<unrecognized:{normalized}>")


def main() -> int:
    _load_env_file(ROOT / ".env.local")
    _load_env_file(ROOT / ".env")

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("MONGO_URI is not configured.", file=sys.stderr)
        return 1

    client = MongoClient(uri, serverSelectionTimeoutMS=15_000)
    try:
        collection = client[DB_NAME][COLLECTION_NAME]
        total_documents = collection.count_documents({})
        counts = Counter(
            _normalize_year(document.get("year"))
            for document in collection.find({}, {"_id": 0, "year": 1})
        )
    finally:
        client.close()

    canonical_total = sum(counts[year] for year in CANONICAL_YEARS)
    print(f"Database: {DB_NAME}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Total player documents: {total_documents}")
    print()
    print("Canonical year breakdown:")
    for year in CANONICAL_YEARS:
        print(f"  {year.capitalize():10} {counts[year]:5}")
    print(f"  {'Canonical total':10} {canonical_total:5}")

    other_counts = {
        label: count
        for label, count in sorted(counts.items())
        if label not in CANONICAL_YEARS
    }
    print()
    if other_counts:
        print("Missing or unrecognized year values:")
        for label, count in other_counts.items():
            print(f"  {label:30} {count:5}")
    else:
        print("Missing or unrecognized year values: 0")

    accounted_for = canonical_total + sum(other_counts.values())
    if accounted_for != total_documents:
        print(
            f"ERROR: counted {accounted_for} of {total_documents} documents.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
