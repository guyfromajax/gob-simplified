"""
Normalize year values to full words: SR→senior, JR→junior, SO→sophomore, FR→freshman.
1. Updates teams/all_players_with_team_names.txt (year column, index 2 only).
2. Updates gob-staging.players collection (year field).
Requires --yes to run. Does not touch FPD/FTD.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_root = str(ROOT)
sys.path.insert(0, _root)
from scripts.db_migration_cli import connect_migration_target

YEAR_ABBR_TO_FULL = {
    "SR": "senior",
    "JR": "junior",
    "SO": "sophomore",
    "FR": "freshman",
}

TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
YEAR_COLUMN_INDEX = 2


def normalize_tsv(*, apply=False):
    with open(TSV_PATH) as f:
        lines = f.readlines()
    if not lines:
        return 0
    out = [lines[0].rstrip("\n\r")]
    changed = 0
    for line in lines[1:]:
        line = line.rstrip("\n\r")
        if not line:
            out.append(line)
            continue
        parts = line.split("\t")
        if len(parts) <= YEAR_COLUMN_INDEX:
            out.append(line)
            continue
        val = parts[YEAR_COLUMN_INDEX].strip().upper()
        full = YEAR_ABBR_TO_FULL.get(val)
        if full is not None:
            parts[YEAR_COLUMN_INDEX] = full
            changed += 1
        out.append("\t".join(parts))
    if apply:
        with open(TSV_PATH, "w") as f:
            f.write("\n".join(out) + "\n")
    return changed


def normalize_gob_staging_players(coll, *, apply=False):
    total = 0
    for abbr, full in YEAR_ABBR_TO_FULL.items():
        total += coll.update_many({"year": abbr}, {"$set": {"year": full}}).modified_count if apply else coll.count_documents({"year": abbr})
    return total, len(YEAR_ABBR_TO_FULL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target("gob-staging", write=args.apply)
    tsv_changed = normalize_tsv(apply=args.apply)
    print(f"[TSV] Updated year column for {tsv_changed} rows in {TSV_PATH}.")
    try:
        db_changed, _ = normalize_gob_staging_players(connection.database["players"], apply=args.apply)
        print(f"[gob-staging.players] Updated year field for {db_changed} documents.")
    except Exception as e:
        print(f"[gob-staging.players] Error: {e}")
        sys.exit(1)
    print("Done.")
    connection.close()


if __name__ == "__main__":
    main()
