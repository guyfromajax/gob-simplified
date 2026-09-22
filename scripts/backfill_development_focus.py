#!/usr/bin/env python3
"""
Backfill Development Focus fields on franchise_players_data (FPD) documents.

Sets two fields, and ONLY when they are missing:
  training_position  the coach-facing training slot; position_intent when present,
                     else the highest position_ratings entry
  training_focus     "standard"

ADDITIVE AND IDEMPOTENT. Every write is a ``$set`` of a field the document does not
have. Nothing is deleted, nothing pre-existing is overwritten, and a second run is a
no-op. Documents that already carry a field keep their value, including a coach's own
choice made through the UI.

TIE-BREAK IS DETERMINISTIC. The plan calls for ties between equal position_ratings to
be resolved randomly once, at backfill. "Randomly" here is seeded from the document id,
so the tie resolves arbitrarily across the population but identically on every run —
which is what lets the dry run below predict exactly what an --apply would write.

Usage:
  python scripts/backfill_development_focus.py --db gob-staging            # dry run
  python scripts/backfill_development_focus.py --db gob-staging --apply    # writes
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Optional

from pymongo import UpdateOne

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target  # noqa: E402

from BackEnd.constants.training_shape import (  # noqa: E402
    DEFAULT_TRAINING_FOCUS,
    POSITIONS,
    TRAINING_FOCUSES,
    derive_training_position,
)

COLLECTION = "franchise_players_data"
SAMPLE_LIMIT = 8
BATCH_SIZE = 1000

# Only documents still missing a field are scanned. That keeps the cursor short-lived (an
# earlier per-document version held one open across all 173k docs and Atlas expired it with
# CursorNotFound at the 10-minute idle limit) and makes a re-run naturally resumable: the
# working set shrinks to whatever is left.
MISSING_FILTER = {"$or": [{"training_position": {"$exists": False}},
                          {"training_focus": {"$exists": False}}]}


def resolve_position(doc: Mapping[str, Any]) -> tuple[Optional[str], str]:
    """Return ``(position, source)`` for one FPD doc.

    The VALUE comes from ``derive_training_position`` — the same helper the runtime
    creation paths use (``carry_dev_fields``), so a backfilled doc and a newly created one
    can never disagree. This function only adds the reporting label.

    source is one of: intent | ratings | ratings-tie | none
    """
    position = derive_training_position(doc)
    if position is None:
        return None, "none"

    intent = doc.get("position_intent")
    if isinstance(intent, str) and intent.strip() in POSITIONS:
        return position, "intent"

    ratings = doc.get("position_ratings") or {}
    usable = {p: v for p, v in ratings.items() if p in POSITIONS and isinstance(v, (int, float))}
    best = max(usable.values())
    tied = [p for p, v in usable.items() if v == best]
    return position, "ratings-tie" if len(tied) > 1 else "ratings"


def backfill(*, db_name: str, dry_run: bool) -> dict[str, Any]:
    connection = connect_migration_target(db_name, write=not dry_run)
    collection = connection.database[COLLECTION]

    stats: Counter = Counter()
    by_position: Counter = Counter()
    by_source: Counter = Counter()
    samples: list[str] = []

    projection = {"position_intent": 1, "position_ratings": 1, "training_position": 1, "training_focus": 1}
    pending: list[UpdateOne] = []

    def flush() -> None:
        if pending and not dry_run:
            collection.bulk_write(pending, ordered=False)
        pending.clear()

    stats["scanned_all_docs"] = collection.count_documents({})
    for doc in collection.find(MISSING_FILTER, projection).batch_size(BATCH_SIZE):
        stats["total_docs"] += 1  # docs still missing at least one field
        updates: dict[str, Any] = {}

        has_pos = isinstance(doc.get("training_position"), str) and doc["training_position"] in POSITIONS
        has_foc = isinstance(doc.get("training_focus"), str) and doc["training_focus"] in TRAINING_FOCUSES

        if has_pos:
            stats["training_position_already_set"] += 1
        else:
            position, source = resolve_position(doc)
            by_source[source] += 1
            if position is None:
                stats["skipped_no_position_source"] += 1
            else:
                updates["training_position"] = position
                by_position[position] += 1

        if has_foc:
            stats["training_focus_already_set"] += 1
        else:
            updates["training_focus"] = DEFAULT_TRAINING_FOCUS

        if not updates:
            stats["no_change"] += 1
            continue

        stats["would_update" if dry_run else "updated"] += 1
        if len(samples) < SAMPLE_LIMIT:
            samples.append(f"    _id={doc.get('_id')} {updates}")
        if dry_run:
            continue

        pending.append(UpdateOne({"_id": doc["_id"]}, {"$set": updates}))
        if len(pending) >= BATCH_SIZE:
            flush()

    flush()

    return {
        "stats": dict(stats),
        "by_position": dict(by_position),
        "by_source": dict(by_source),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill FPD training_position / training_focus")
    parser.add_argument("--db", default="gob-staging", choices=("gob-staging", "gob"))
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run")
    args = parser.parse_args()

    dry_run = not args.apply
    mode = "DRY RUN" if dry_run else "WRITE"
    print(f"[{mode}] backfill {COLLECTION} training_position / training_focus on db={args.db!r}")

    result = backfill(db_name=args.db, dry_run=dry_run)
    s = result["stats"]
    print("\n  counts")
    for key in ("scanned_all_docs", "total_docs", "training_position_already_set", "training_focus_already_set",
                "skipped_no_position_source", "no_change", "would_update", "updated"):
        if key in s:
            print(f"    {key:32} {s[key]:>8}")
    print("\n  position resolved from")
    for key, n in sorted(result["by_source"].items()):
        print(f"    {key:32} {n:>8}")
    print("\n  training_position to be written")
    for key in POSITIONS:
        if key in result["by_position"]:
            print(f"    {key:32} {result['by_position'][key]:>8}")
    if result["samples"]:
        print("\n  sample writes")
        for line in result["samples"]:
            print(line)
    if dry_run:
        print("\n  nothing was written. re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
