"""
Increase all 12 player attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT)
by 8% for non-Conference 1 teams in teams/all_players_with_team_names.txt.
Formula: new = min(100, round(old * 1.08)). Conference 1 rows unchanged.
"""
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")

# Conference 1 (core-8) teams — unchanged
CONFERENCE_1 = {
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
}
# Column indices for the 12 attributes (no player_type: height=4, weight=5, SC..FT=6–17, team=18)
ATTR_INDICES = list(range(6, 18))
TEAM_INDEX = 18
FACTOR = 1.08
MAX_ATTR = 100


def main():
    with open(TSV_PATH) as f:
        lines = f.readlines()
    if not lines:
        print("File empty.")
        return
    out = [lines[0].rstrip("\n\r")]  # header unchanged
    changed = 0
    for line in lines[1:]:
        line = line.rstrip("\n\r")
        if not line:
            out.append(line)
            continue
        parts = line.split("\t")
        if len(parts) <= TEAM_INDEX:
            out.append(line)
            continue
        team = parts[TEAM_INDEX].strip()
        if team in CONFERENCE_1:
            out.append(line)
            continue
        for i in ATTR_INDICES:
            try:
                v = int(parts[i])
            except (ValueError, TypeError):
                continue
            new_v = min(MAX_ATTR, round(v * FACTOR))
            parts[i] = str(new_v)
        out.append("\t".join(parts))
        changed += 1
    with open(TSV_PATH, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"Increased attributes by 8% for {changed} players (non-Conference 1). File: {TSV_PATH}")


if __name__ == "__main__":
    main()
