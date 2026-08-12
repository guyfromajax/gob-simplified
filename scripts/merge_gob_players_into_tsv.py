"""
1. Remove the player_type column from teams/all_players_with_team_names.txt.
2. Pull every document from gob.players and append rows to that TSV so all players
   are in one file.

Output TSV columns: first_name, last_name, year, jersey, height, weight,
SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, team

SAFETY: Reads existing file and gob.players, then overwrites the TSV with
merged content. Does not touch any database except read from gob.players.

Run from repo root:
  GOB_DB_ACCESS=read python3 scripts/merge_gob_players_into_tsv.py --db gob
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

TSV_PATH = ROOT / "teams" / "all_players_with_team_names.txt"
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]


def _int(v, default=0):
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _strip(s):
    return (s or "").strip()


def remove_player_type_from_lines(lines):
    """Remove column at index 4 (player_type) from header and each data row. Return (header_line, data_rows)."""
    if not lines:
        return "", []
    header = lines[0]
    parts = header.split("\t")
    if "player_type" in parts:
        idx = parts.index("player_type")
        parts.pop(idx)
        new_header = "\t".join(parts)
    else:
        new_header = header
    data_rows = []
    for line in lines[1:]:
        if not line.strip():
            continue
        row = line.split("\t")
        if len(row) > 4:
            row.pop(4)  # player_type at index 4
        data_rows.append("\t".join(row))
    return new_header, data_rows


def player_doc_to_tsv_row(p):
    """Build a TSV row from a gob.players document. No player_type column."""
    attrs = p.get("attributes") or {}
    return "\t".join([
        _strip(p.get("first_name")),
        _strip(p.get("last_name")),
        _strip(p.get("year", "")),
        str(_int(p.get("jersey"), 0)),
        str(_int(p.get("height"), 75)),
        str(_int(p.get("weight"), 200)),
        *(str(_int(attrs.get(k), 0)) for k in ATTR_KEYS),
        _strip(p.get("team", "")),
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, choices=["gob-staging", "gob"])
    args = parser.parse_args()
    if not TSV_PATH.exists():
        print(f"❌ File not found: {TSV_PATH}")
        sys.exit(1)
    connection = connect_migration_target(args.db, write=False)

    with open(TSV_PATH) as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]

    # 1) Remove player_type from existing content
    new_header, existing_rows = remove_player_type_from_lines(lines)
    # Normalize header: use 'team' for last column if it was team_link
    if new_header.endswith("team_link"):
        new_header = new_header.replace("team_link", "team")
    print(f"Existing rows (after dropping player_type): {len(existing_rows)}")

    # 2) Fetch all players from gob.players
    gob_players = list(connection.database["players"].find({}))
    connection.close()
    print(f"[{args.db}] Fetched {len(gob_players)} player(s).")

    # 3) Build rows for gob players (skip if no team name)
    gob_rows = []
    for p in gob_players:
        if not _strip(p.get("team")):
            continue
        gob_rows.append(player_doc_to_tsv_row(p))

    # 4) Write merged file: header + existing rows + gob rows
    out_lines = [new_header] + existing_rows + gob_rows
    with open(TSV_PATH, "w") as f:
        f.write("\n".join(out_lines) + "\n")

    print(f"Wrote {len(out_lines) - 1} total data rows to {TSV_PATH} (header + {len(existing_rows)} existing + {len(gob_rows)} from gob).")
    print("Done.")


if __name__ == "__main__":
    main()
