"""
Add total_player_attrs to each document in the teams collection in gob-staging,
using values from docs/To Do/total_team_attrs.md (first table: "Total team attributes" column).

Run from repo root with venv activated: python scripts/add_total_player_attrs_to_teams_gob_staging.py
"""
import os
import sys
import re

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

# Force gob-staging so we only touch staging
os.environ["MONGO_DB_NAME"] = "gob-staging"

from BackEnd.db import db

DB_NAME = "gob-staging"
DOC_PATH = os.path.join(_root, "docs", "To Do", "total_team_attrs.md")


def parse_total_attrs_from_md():
    """Parse first markdown table in total_team_attrs.md: Team -> Total team attributes."""
    with open(DOC_PATH) as f:
        content = f.read()
    # First table: | Rank | Team | Total team attributes | Prestige |
    lines = content.split("\n")
    name_to_total = {}
    in_first_table = False
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            if in_first_table:
                break
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if "Rank" in parts and "Team" in parts and "Total team attributes" in parts:
            in_first_table = True
            continue
        if not in_first_table or len(parts) < 4:
            continue
        # Skip separator row (all digits or dashes)
        if re.match(r"^\d+$", parts[0]) and re.match(r"^\d+$", parts[2]):
            rank = int(parts[0])
            team_name = parts[1]
            total_attrs = int(parts[2])
            name_to_total[team_name] = total_attrs
    return name_to_total


def main():
    if db.name != DB_NAME:
        print(f"❌ DB is '{db.name}'. Set MONGO_DB_NAME=gob-staging (or use .env.local) to target gob-staging.")
        sys.exit(1)
    name_to_total = parse_total_attrs_from_md()
    print(f"Parsed {len(name_to_total)} team names from {DOC_PATH}")
    teams_coll = db["teams"]
    all_teams = list(teams_coll.find({}, {"_id": 1, "name": 1}))
    print(f"Found {len(all_teams)} documents in {DB_NAME}.teams")
    updated = 0
    missing = []
    for doc in all_teams:
        name = doc.get("name")
        if not name:
            missing.append((str(doc.get("_id")), "(no name)"))
            continue
        if name not in name_to_total:
            missing.append((name, "(not in doc)"))
            continue
        value = name_to_total[name]
        teams_coll.update_one({"_id": doc["_id"]}, {"$set": {"total_player_attrs": value}})
        updated += 1
    print(f"Updated {updated} team documents with total_player_attrs.")
    if missing:
        print(f"⚠️ No value set for {len(missing)} teams: {missing[:10]}{'...' if len(missing) > 10 else ''}")


if __name__ == "__main__":
    main()
