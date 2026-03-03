"""
Build total team attributes (sum of SC,SH,ID,OD,PS,BH,RB,ST,AG,ND,IQ,FT per team),
stack-rank teams, add prestige from gob-staging teams. Output: docs/To Do/total_team_attrs.md
"""
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

DB_NAME = "gob-staging"
CORE_8 = {
    "Bentley-Truman", "Morristown", "Four Corners", "South Lancaster",
    "Lancaster", "Xavien", "Little York", "Ocean City",
}
ATTR_KEYS = ["SC", "SH", "ID", "OD", "PS", "BH", "RB", "ST", "AG", "ND", "IQ", "FT"]
TSV_PATH = os.path.join(_root, "teams", "all_players_with_team_names.txt")
OUT_PATH = os.path.join(_root, "docs", "To Do", "total_team_attrs.md")

def _int(s, default=0):
    try:
        return int(s)
    except (ValueError, TypeError):
        return default

def main():
    team_totals = {}
    # Indices in TSV: 7-18 = SC..FT, 19 = team name
    idx_attrs = list(range(7, 19))
    with open(TSV_PATH) as f:
        lines = [ln.rstrip("\n\r") for ln in f.readlines()]
    for line in lines[1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) <= 19:
            continue
        team_name = parts[19].strip()
        if team_name in CORE_8:
            continue
        s = sum(_int(parts[i], 0) for i in idx_attrs)
        team_totals[team_name] = team_totals.get(team_name, 0) + s

    # Core 8: from gob-staging players
    if client:
        players = client[DB_NAME]["players"]
        teams_coll = client[DB_NAME]["teams"]
        for team_name in CORE_8:
            cursor = players.find({"team": team_name}, {"attributes": 1})
            t = 0
            for doc in cursor:
                attrs = doc.get("attributes") or {}
                t += sum(_int(attrs.get(k), 0) for k in ATTR_KEYS)
            team_totals[team_name] = team_totals.get(team_name, 0) + t

        # Prestige per team
        prestige_by_name = {}
        for doc in teams_coll.find({}, {"name": 1, "prestige": 1}):
            prestige_by_name[doc.get("name", "")] = doc.get("prestige", 0)
    else:
        prestige_by_name = {t: 0 for t in team_totals}

    # Sort by total desc, assign rank
    sorted_teams = sorted(team_totals.items(), key=lambda x: -x[1])
    rows = []
    for rank, (name, total) in enumerate(sorted_teams, 1):
        rows.append((rank, name, total, prestige_by_name.get(name, "")))

    # Write markdown table
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        f.write("| Rank | Team | Total team attributes | Prestige |\n")
        f.write("|------|------|----------------------|----------|\n")
        for r, name, total, prestige in rows:
            f.write(f"| {r} | {name} | {total} | {prestige} |\n")
    print(f"Wrote {OUT_PATH} ({len(rows)} teams).")

if __name__ == "__main__":
    main()
