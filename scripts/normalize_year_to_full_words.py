"""
Normalize year values to full words: SR→senior, JR→junior, SO→sophomore, FR→freshman.
1. Updates teams/all_players_with_team_names.txt (year column, index 2 only).
2. Updates gob-staging.players collection (year field).
Requires --yes to run. Does not touch FPD/FTD.
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)

for path in [".env.local", ".env"]:
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

YEAR_ABBR_TO_FULL = {
    "SR": "senior",
    "JR": "junior",
    "SO": "sophomore",
    "FR": "freshman",
}

TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
YEAR_COLUMN_INDEX = 2


def normalize_tsv():
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
    with open(TSV_PATH, "w") as f:
        f.write("\n".join(out) + "\n")
    return changed


def normalize_gob_staging_players():
    from BackEnd.db import client
    if not client:
        return 0, 0
    coll = client["gob-staging"]["players"]
    total = 0
    for abbr, full in YEAR_ABBR_TO_FULL.items():
        result = coll.update_many({"year": abbr}, {"$set": {"year": full}})
        total += result.modified_count
    return total, len(YEAR_ABBR_TO_FULL)


def main():
    if "--yes" not in sys.argv:
        print("Normalizes year to full words (TSV + gob-staging.players). Requires --yes.")
        sys.exit(1)
    tsv_changed = normalize_tsv()
    print(f"[TSV] Updated year column for {tsv_changed} rows in {TSV_PATH}.")
    try:
        db_changed, _ = normalize_gob_staging_players()
        print(f"[gob-staging.players] Updated year field for {db_changed} documents.")
    except Exception as e:
        print(f"[gob-staging.players] Error: {e}")
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()
