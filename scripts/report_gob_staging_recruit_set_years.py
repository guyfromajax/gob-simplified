#!/usr/bin/env python3
"""Read-only year breakdown for gob-staging.recruit_sets set_0001."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

COLLECTION_NAME = "recruit_sets"
SET_ID = "set_0001"
YEAR_ORDER = ("JH", "FR", "SO", "JR", "SR")
YEAR_ALIASES = {
    "jh": "JH",
    "junior high": "JH",
    "junior_high": "JH",
    "fr": "FR",
    "fresh": "FR",
    "freshman": "FR",
    "so": "SO",
    "soph": "SO",
    "sophomore": "SO",
    "jr": "JR",
    "junior": "JR",
    "sr": "SR",
    "senior": "SR",
}


def _normalize_year(value: object) -> str:
    if value is None:
        return "<missing>"
    normalized = str(value).strip().lower().replace(".", "")
    if not normalized:
        return "<missing>"
    return YEAR_ALIASES.get(normalized, f"<unrecognized:{normalized}>")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    connection = connect_migration_target(args.db, write=False)
    try:
        collection = connection.database[COLLECTION_NAME]
        documents = list(
            collection.find(
                {"set_id": SET_ID},
                {"_id": 1, "set_id": 1, "recruit_count": 1, "recruits.year": 1},
            )
        )
    finally:
        connection.close()

    if len(documents) != 1:
        print(
            f"Expected exactly one {args.db}.{COLLECTION_NAME} document with "
            f"set_id={SET_ID!r}; found {len(documents)}.",
            file=sys.stderr,
        )
        return 2

    document = documents[0]
    recruits = document.get("recruits") or []
    counts = Counter(_normalize_year(recruit.get("year")) for recruit in recruits)
    canonical_total = sum(counts[year] for year in YEAR_ORDER)
    other_counts = {
        label: count
        for label, count in sorted(counts.items())
        if label not in YEAR_ORDER
    }

    print(f"Database: {args.db}")
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Set: {document.get('set_id')} (Mongo _id: {document.get('_id')})")
    print(f"Declared recruit_count: {document.get('recruit_count')}")
    print(f"Actual recruits array length: {len(recruits)}")
    print()
    print("Recruit year breakdown:")
    for year in YEAR_ORDER:
        print(f"  {year:2} {counts[year]:5}")
    print(f"  {'Total':5} {canonical_total:5}")
    print()
    if other_counts:
        print("Missing or unrecognized year values:")
        for label, count in other_counts.items():
            print(f"  {label:30} {count:5}")
    else:
        print("Missing or unrecognized year values: 0")

    accounted_for = canonical_total + sum(other_counts.values())
    if accounted_for != len(recruits):
        print(
            f"ERROR: counted {accounted_for} of {len(recruits)} recruits.",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
