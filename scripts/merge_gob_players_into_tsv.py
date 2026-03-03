"""
1. Remove the player_type column from teams/all_players_with_team_names.txt.
2. Pull every document from gob.players and append rows to that TSV so all players
   are in one file.

Output TSV columns: first_name, last_name, year, jersey, height, weight,
SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT, team

SAFETY: Reads existing file and gob.players, then overwrites the TSV with
merged content. Does not touch any database except read from gob.players.

Run from repo root: python3 scripts/merge_gob_players_into_tsv.py
"""
import os
import sys

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
sys.path.insert(0, _root)
os.chdir(_root)


def _load_env(filepath):
    out = {}
    if os.path.exists(filepath):
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    return out


for path in [".env.local", ".env"]:
    for k, v in _load_env(path).items():
        os.environ.setdefault(k, v)

from BackEnd.db import client

TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
GOB_DB = "gob"
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
    if not os.path.exists(TSV_PATH):
        print(f"❌ File not found: {TSV_PATH}")
        sys.exit(1)
    if not client:
        print("❌ MongoDB client not available.")
        sys.exit(1)

    with open(TSV_PATH) as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]

    # 1) Remove player_type from existing content
    new_header, existing_rows = remove_player_type_from_lines(lines)
    # Normalize header: use 'team' for last column if it was team_link
    if new_header.endswith("team_link"):
        new_header = new_header.replace("team_link", "team")
    print(f"Existing rows (after dropping player_type): {len(existing_rows)}")

    # 2) Fetch all players from gob.players
    gob_players = list(client[GOB_DB]["players"].find({}))
    print(f"[{GOB_DB}] Fetched {len(gob_players)} player(s).")

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
