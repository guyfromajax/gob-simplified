"""
Re-populate gob-staging universal teams collection from teams/128_teams.txt.
Upserts 128 teams on the stable ``team_id`` slug with: name, mascot, team_id,
primary_color, secondary_color, region, conference, prestige, player_ids, and
zeroed team attributes (for Single/Tournament/Franchise init). Slugs absent from
the TSV are deleted.

Existing ObjectIds are PRESERVED. Do not go back to delete_many + insert_many:
_id churn here propagates to production via publish_universal_data.py and orphans
`user_team_object_id` / FTD `team_id` on every franchise created before the reseed.

TSV columns: id, team, mascot, team_id, primary_color, secondary_color, conference, region, prestige
Region is letter (A–H). Run from repo root: python3 scripts/repopulate_teams_gob_staging.py
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_root = str(ROOT)
sys.path.insert(0, _root)
from scripts.db_migration_cli import connect_migration_target

TEAM_ATTR_KEYS = [
    "shot_threshold", "discipline", "fight", "rebound_modifier",
    "momentum_score", "offensive_efficiency", "team_chemistry", "defensive_efficiency",
    "fb_efficiency", "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier",
]
TEAM_ATTRS_ZERO = {k: 0 for k in TEAM_ATTR_KEYS}

DB_NAME = "gob-staging"
TEAMS_FILE = os.path.join(_root, "teams", "128_teams.txt")


def parse_row(line):
    parts = line.strip().split("\t")
    if len(parts) < 9:
        return None
    try:
        return {
            "id": int(parts[0]),
            "name": parts[1].strip(),
            "mascot": parts[2].strip(),
            "team_id": parts[3].strip(),
            "primary_color": parts[4].strip(),
            "secondary_color": parts[5].strip(),
            "conference": int(parts[6]),
            "region": parts[7].strip(),
            "prestige": int(parts[8]),
        }
    except (ValueError, IndexError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not os.path.exists(TEAMS_FILE):
        print(f"❌ File not found: {TEAMS_FILE}")
        sys.exit(1)

    connection = connect_migration_target(DB_NAME, write=args.apply)
    teams_coll = connection.database["teams"]
    with open(TEAMS_FILE) as f:
        lines = f.readlines()

    rows = []
    for line in lines[1:]:
        row = parse_row(line)
        if row:
            rows.append(row)

    if len(rows) != 128:
        print(f"⚠️ Expected 128 rows, got {len(rows)}. Proceeding anyway.")

    # Upsert on the stable ``team_id`` slug so existing ObjectIds SURVIVE a reseed.
    # The old delete_many + insert_many minted fresh _ids every run; publish_universal_data
    # then copies those _ids into production, orphaning `user_team_object_id` and every FTD
    # `team_id` on franchises created before the reseed (they render raw ObjectIds and blank
    # opponents). replace_one keeps the matched doc's _id while producing a document
    # byte-identical to what insert_many used to write.
    slugs = [row["team_id"] for row in rows]
    duplicate_slugs = {s for s in slugs if slugs.count(s) > 1}
    if duplicate_slugs:
        print(f"⚠️ Duplicate team_id slug(s) in TSV: {sorted(duplicate_slugs)}. Last row wins.")

    inserted = 0
    updated = 0
    for row in rows:
        doc = {
            "name": row["name"],
            "mascot": row["mascot"],
            "team_id": row["team_id"],
            "primary_color": row["primary_color"],
            "secondary_color": row["secondary_color"],
            "region": row["region"],
            "conference": row["conference"],
            "prestige": row["prestige"],
            "player_ids": [],
            **TEAM_ATTRS_ZERO,
        }
        if args.apply:
            result = teams_coll.replace_one({"team_id": row["team_id"]}, doc, upsert=True)
            if result.upserted_id is not None:
                inserted += 1
            else:
                updated += 1
        elif teams_coll.count_documents({"team_id": row["team_id"]}, limit=1):
            updated += 1
        else:
            inserted += 1

    verb = "Kept _id on" if args.apply else "Would keep _id on"
    print(f"[{DB_NAME}] {verb} {updated} existing team(s); "
          f"{'inserted' if args.apply else 'would insert'} {inserted} new team(s).")

    # Slugs no longer in the TSV must go, or the collection drifts past 128.
    stale_filter = {"team_id": {"$nin": slugs}}
    stale = teams_coll.count_documents(stale_filter)
    if stale:
        if args.apply:
            teams_coll.delete_many(stale_filter)
        print(f"[{DB_NAME}] {'Deleted' if args.apply else 'Would delete'} "
              f"{stale} team(s) whose slug is absent from the TSV.")

    label = "Total teams" if args.apply else "Total teams (before any change)"
    print(f"[{DB_NAME}] {label}: {teams_coll.count_documents({})}")
    print("Done." if args.apply else "Dry run — pass --apply to write.")
    connection.close()


if __name__ == "__main__":
    main()
