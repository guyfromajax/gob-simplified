#!/usr/bin/env python3
"""
Update the region field on documents in the universal teams collection in gob-staging
to match teams/128_teams.txt. Matches teams by name (school column).

Run from repo root with MONGO_URI set (e.g. in .env or .env.local):
  .venv/bin/python scripts/sync_team_regions_to_gob_staging.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

def _load_env(filepath: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if filepath.exists():
        for line in filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for p in [ROOT / ".env.local", ROOT / ".env"]:
    for k, v in _load_env(p).items():
        os.environ.setdefault(k, v)

from pymongo import MongoClient

DB_NAME = "gob-staging"
TSV_PATH = ROOT / "teams" / "128_teams.txt"
# Column indices: id=0, school=1, mascot=2, team_id=3, ..., region=7, prestige=8
IDX_SCHOOL = 1
IDX_REGION = 7


def main() -> int:
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("❌ MONGO_URI not set. Set it in .env or .env.local", file=sys.stderr)
        return 1
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

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    teams_coll = client[DB_NAME]["teams"]

    updated = 0
    not_found = 0
    for school, region in school_to_region.items():
        result = teams_coll.update_one(
            {"name": school},
            {"$set": {"region": region}},
        )
        if result.matched_count:
            updated += 1
        else:
            not_found += 1
            print(f"  ⚠ No team named '{school}' in {DB_NAME}.teams", file=sys.stderr)

    print(f"✅ Updated region for {updated} teams in {DB_NAME}.teams")
    if not_found:
        print(f"   {not_found} schools from TSV had no matching team document.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
