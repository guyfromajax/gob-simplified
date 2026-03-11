"""
Update only the 12 attribute values (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT)
for the 96 Conference 1 players in teams/all_players_with_team_names.txt,
pulling values from each team's staging.json in the teams folder.

Conference 1 = 8 teams; only those rows are modified. All other columns unchanged.
"""
import json
import os

_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_script_dir)
TEAMS_DIR = os.path.join(_root, "teams")
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")

CONFERENCE_1 = {
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
}

STAGING_FILES = [
    "bentley_truman_staging.json",
    "four_corners_staging.json",
    "lancaster_staging.json",
    "little_york_staging.json",
    "morristown_staging.json",
    "ocean_city_staging.json",
    "south_lancaster_staging.json",
    "xavien_staging.json",
]

ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
# TSV columns: first_name last_name year jersey player_type height weight SC..FT team (19 cols, 0-18)
# 0-based: 0=first_name, 1=last_name, 2=year, 3=jersey, 4=player_type, 5=height, 6=weight,
#          7=SC .. 18=FT (12 attrs at 7-18 in header order; data has attrs at 6-17, team at 18)
# Actual data: 19 fields; attrs at 6-17, team at 18.
ATTR_START = 6
ATTR_END = 18  # exclusive (attrs at 6..17)
TEAM_INDEX = 18


def load_staging_lookup():
    """Build (first_name, last_name, team) -> [SC, SH, ..., FT] from all 8 staging JSONs."""
    lookup = {}
    for filename in STAGING_FILES:
        path = os.path.join(TEAMS_DIR, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path) as f:
            data = json.load(f)
        team_name = data.get("name", "").strip()
        if team_name not in CONFERENCE_1:
            continue
        for p in data.get("players", []):
            fn = (p.get("first_name") or "").strip()
            ln = (p.get("last_name") or "").strip()
            key = (fn, ln, team_name)
            vals = [int(p.get(k, 0)) for k in ATTR_KEYS]
            lookup[key] = vals
    return lookup


def main():
    staging_lookup = load_staging_lookup()
    print(f"Loaded {len(staging_lookup)} Conference 1 players from staging JSONs.")

    with open(TSV_PATH) as f:
        lines = f.readlines()
    if not lines:
        print("TSV empty.")
        return
    header = lines[0].rstrip("\n\r")
    out_lines = [header + "\n"]
    updated = 0
    for line in lines[1:]:
        line = line.rstrip("\n\r")
        parts = line.split("\t")
        if len(parts) <= TEAM_INDEX:
            out_lines.append(line + "\n")
            continue
        team = parts[TEAM_INDEX].strip()
        if team not in CONFERENCE_1:
            out_lines.append(line + "\n")
            continue
        first_name = (parts[0] or "").strip()
        last_name = (parts[1] or "").strip()
        key = (first_name, last_name, team)
        if key not in staging_lookup:
            out_lines.append(line + "\n")
            continue
        attr_vals = staging_lookup[key]
        for i, val in enumerate(attr_vals):
            parts[ATTR_START + i] = str(val)
        out_lines.append("\t".join(parts) + "\n")
        updated += 1

    with open(TSV_PATH, "w") as f:
        f.writelines(out_lines)
    print(f"Updated {updated} Conference 1 rows (12 attributes each) in {TSV_PATH}.")


if __name__ == "__main__":
    main()
