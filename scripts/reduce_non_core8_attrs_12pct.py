"""
Reduce all 12 player attributes (SC, SH, ID, OD, PS, BH, RB, ST, AG, ND, IQ, FT)
by 12% for non-core-8 teams in teams/all_players_with_team_names.txt.
Formula: new = max(1, round(old * 0.88)). Core-8 rows unchanged.
"""
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")

CORE_8 = {
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
}
ATTR_INDICES = list(range(7, 19))  # SC through FT
FACTOR = 0.88

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
        if len(parts) <= 19:
            out.append(line)
            continue
        team = parts[19].strip()
        if team in CORE_8:
            out.append(line)
            continue
        for i in ATTR_INDICES:
            try:
                v = int(parts[i])
            except (ValueError, TypeError):
                continue
            new_v = max(1, round(v * FACTOR))
            parts[i] = str(new_v)
        out.append("\t".join(parts))
        changed += 1
    with open(TSV_PATH, "w") as f:
        f.write("\n".join(out) + "\n")
    print(f"Reduced attributes by 12% for {changed} players (non-core-8). File: {TSV_PATH}")

if __name__ == "__main__":
    main()
