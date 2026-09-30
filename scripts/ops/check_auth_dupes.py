#!/usr/bin/env python3
"""Report duplicates that would block the auth unique indexes. READ-ONLY.

The app now creates unique indexes on users.email and alpha_otps.otp_code at
startup. If duplicates exist, index creation logs a WARNING and the index is simply
not enforced. Run this against a database BEFORE deploying, resolve anything it
lists by hand, then deploy.

Reports, per collection:
  - exact duplicates (block the index)
  - case/whitespace-variant duplicates (don't block it, but are logically the same
    account / code: signup lower-cases emails, codes are upper-cased)
  - documents missing the field (several would collide on null)
  - the collection's existing indexes (an existing non-unique index on the same key
    under another name makes the create fail with an options conflict)

Usage:
  ../gob-simplified/.venv/bin/python scripts/ops/check_auth_dupes.py --db gob-staging
  GOB_DB_ACCESS=read ../gob-simplified/.venv/bin/python scripts/ops/check_auth_dupes.py --db gob

Never writes. Opens the database with access="read".
Exit code: 0 = clean, 1 = something would block an index, 2 = connection error.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CHECKS = (
    # collection, field, normalizer description, normalizer
    ("users", "email", "lower+strip", lambda v: str(v).strip().lower()),
    ("alpha_otps", "otp_code", "upper+strip", lambda v: str(v).strip().upper()),
)


def _groups(values: dict[Any, list]) -> list[dict]:
    return [
        {"value": value, "count": len(ids), "ids": [str(i) for i in ids]}
        for value, ids in sorted(values.items(), key=lambda kv: str(kv[0]))
        if len(ids) > 1
    ]


def find_auth_dupes(db: Any) -> dict:
    """Pure read: {collection: {exact, variant, missing, indexes}}."""
    report: dict = {}
    for coll_name, field, norm_label, normalize in CHECKS:
        coll = db[coll_name]
        exact: dict[Any, list] = defaultdict(list)
        variant: dict[Any, list] = defaultdict(list)
        raw_spellings: dict[Any, set] = defaultdict(set)
        missing: list = []
        for doc in coll.find({}, {field: 1}):
            value = doc.get(field)
            if value is None or value == "":
                missing.append(doc["_id"])
                continue
            exact[value].append(doc["_id"])
            key = normalize(value)
            variant[key].append(doc["_id"])
            raw_spellings[key].add(str(value))
        exact_groups = _groups(exact)
        # Only groups that differ by case/whitespace (pure exact dupes are listed above).
        variant_groups = [g for g in _groups(variant) if len(raw_spellings[g["value"]]) > 1]
        try:
            indexes = {
                ix.get("name"): {"key": dict(ix.get("key", {})), "unique": bool(ix.get("unique"))}
                for ix in coll.list_indexes()
            }
        except Exception as e:  # pragma: no cover - reporting only
            indexes = {"<error>": str(e)}
        report[coll_name] = {
            "field": field,
            "normalizer": norm_label,
            "exact": exact_groups,
            "variant": variant_groups,
            "missing": [str(i) for i in missing],
            "indexes": indexes,
        }
    return report


def blocks_index(report: dict) -> bool:
    return any(r["exact"] or len(r["missing"]) > 1 for r in report.values())


def _redact(value: Any, show: bool) -> str:
    text = str(value)
    if show or "@" not in text:
        return text
    local, _, domain = text.partition("@")
    return f"{local[:2]}***@{domain}"


def print_report(report: dict, *, show_values: bool, out=sys.stdout) -> None:
    for coll_name, r in report.items():
        print(f"\n== {coll_name}.{r['field']} ==", file=out)
        print(f"  exact duplicates (BLOCK the unique index): {len(r['exact'])}", file=out)
        for g in r["exact"]:
            print(f"    {_redact(g['value'], show_values)!r} x{g['count']}: {', '.join(g['ids'])}", file=out)
        print(f"  {r['normalizer']} variants (same {r['field']} after normalizing): {len(r['variant'])}", file=out)
        for g in r["variant"]:
            print(f"    {_redact(g['value'], show_values)!r} x{g['count']}: {', '.join(g['ids'])}", file=out)
        print(f"  documents missing {r['field']}: {len(r['missing'])}"
              + (" (BLOCKS: more than one null)" if len(r["missing"]) > 1 else ""), file=out)
        for mid in r["missing"]:
            print(f"    {mid}", file=out)
        print("  existing indexes:", file=out)
        for name, spec in r["indexes"].items():
            print(f"    {name}: {spec}", file=out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="Target database name (e.g. gob-staging, gob).")
    parser.add_argument("--show-values", action="store_true", help="Print full emails instead of redacted ones.")
    args = parser.parse_args(argv)

    from BackEnd.script_db import ScriptDatabaseError, connect_script_database

    try:
        connection = connect_script_database(
            target=args.db,
            access="read",
            pristine_env=dict(os.environ),
            repo_root=ROOT,
        )
    except ScriptDatabaseError as e:
        print(f"connection refused: {e}", file=sys.stderr)
        return 2
    try:
        report = find_auth_dupes(connection.database)
    finally:
        connection.close()
    print(f"Auth index duplicate check — database={args.db} (read-only)")
    print_report(report, show_values=args.show_values)
    if blocks_index(report):
        print("\nRESULT: duplicates would block a unique index. Resolve them before deploying.")
        return 1
    print("\nRESULT: clean — both unique indexes can be created.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
