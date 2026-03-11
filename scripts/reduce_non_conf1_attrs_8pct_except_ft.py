"""
Reduce 11 player attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ) by 8%
for non-Conference 1 teams in teams/all_players_with_team_names.txt.
FT is unchanged. Formula: new = max(1, min(100, round(old * 0.92))).
Conference 1 rows unchanged.
"""
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")

CONFERENCE_1 = {
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
}
# TSV: attrs at 6-17 (SC..FT). Reduce only 6-16 (SC..IQ); leave 17 (FT) unchanged.
ATTR_INDICES = list(range(6, 17))
TEAM_INDEX = 18
FACTOR = 0.92
MIN_ATTR, MAX_ATTR = 1, 100


def main():
    with open(TSV_PATH) as f:
        lines = f.readlines()
    if not lines:
        print("File empty.")
        return
    out = [lines[0].rstrip("\n\r")]
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
            new_v = max(MIN_ATTR, min(MAX_ATTR, round(v * FACTOR)))
            parts[i] = str(new_v)
        out.append("\t".join(parts))
        changed += 1
    with open(TSV_PATH, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"Reduced 11 attributes (excl. FT) by 8% for {changed} players (non-Conference 1). File: {TSV_PATH}")


if __name__ == "__main__":
    main()
