#!/usr/bin/env python3
"""
Update the region field on documents in the universal teams collection in gob-staging
to match teams/128_teams.txt. Matches teams by name (school column).

Dry-run is the default. Pass --apply to persist staging changes.
"""

from __future__ import annotations

import os
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from BackEnd.script_db import STAGING_DB, ScriptDatabaseError, connect_script_database

DB_NAME = STAGING_DB
TSV_PATH = ROOT / "teams" / "128_teams.txt"
# Column indices: id=0, school=1, mascot=2, team_id=3, ..., region=7, prestige=8
IDX_SCHOOL = 1
IDX_REGION = 7


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Persist staging updates.")
    args = parser.parse_args()
    if not TSV_PATH.exists():
        print(f"❌ File not found: {TSV_PATH}", file=sys.stderr)
        return 1

    lines = TSV_PATH.read_text(encoding="utf-8").splitlines()
    if not lines or len(lines) < 2:
        print("❌ No data rows in TSV.", file=sys.stderr)
        return 1

    # school name -> region (letter A–H)
    school_to_region: dict[str, str] = {}
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        row = line.split("\t")
        if len(row) <= IDX_REGION:
            continue
        school = row[IDX_SCHOOL].strip()
        region = row[IDX_REGION].strip()
        if school and region:
            school_to_region[school] = region

    connection = connect_script_database(
        target=DB_NAME,
        access="write" if args.apply else "read",
        pristine_env=dict(os.environ),
        repo_root=ROOT,
    )
    teams_coll = connection.database["teams"]

    updated = 0
    not_found = 0
    for school, region in school_to_region.items():
        current = teams_coll.find_one({"name": school}, {"region": 1})
        if current:
            updated += 1
            if args.apply:
                teams_coll.update_one({"_id": current["_id"]}, {"$set": {"region": region}})
        else:
            not_found += 1
            print(f"  ⚠ No team named '{school}' in {DB_NAME}.teams", file=sys.stderr)

    mode = "Updated" if args.apply else "Would update"
    print(f"✅ {mode} region for {updated} teams in {DB_NAME}.teams")
    if not_found:
        print(f"   {not_found} schools from TSV had no matching team document.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ScriptDatabaseError as exc:
        print(f"Refusing unsafe database operation: {exc}", file=sys.stderr)
        sys.exit(2)
