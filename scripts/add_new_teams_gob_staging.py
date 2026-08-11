"""
Add 8 new teams to the universal teams collection in gob-staging only.
All team attribute values are 0 (game/tournament/franchise init overwrites at creation).
Run from repo root: python3 scripts/add_new_teams_gob_staging.py
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.db_migration_cli import connect_migration_target

# All team attribute keys set to 0 for new teams (init overwrites at game/tournament/franchise creation)
TEAM_ATTR_KEYS = [
    "shot_threshold", "discipline", "fight", "rebound_modifier",
    "momentum_score", "offensive_efficiency", "team_chemistry", "defensive_efficiency",
    "fb_efficiency", "pt_efficiency", "fb_opp_modifier", "pt_opp_modifier",
]
TEAM_ATTRS_ZERO = {k: 0 for k in TEAM_ATTR_KEYS}

NEW_TEAMS = [
    {
        "name": "Durham",
        "mascot": "Generals",
        "team_id": "DURHAM",
        "primary_color": "#1c2a44",
        "secondary_color": "#c8a951",
    },
    {
        "name": "IDA",
        "mascot": "Academy",
        "team_id": "IDA",
        "primary_color": "#f2f2f2",
        "secondary_color": "#1f4fb2",
    },
    {
        "name": "Cagers World",
        "mascot": "Mustangs",
        "team_id": "CAGERS_WORLD",
        "primary_color": "#5a3a1b",
        "secondary_color": "#c5c5c5",
    },
    {
        "name": "Casino Row",
        "mascot": "Blackjacks",
        "team_id": "CASINO_ROW",
        "primary_color": "#111111",
        "secondary_color": "#d4af37",
    },
    {
        "name": "Appalachia",
        "mascot": "Rams",
        "team_id": "APPALACHIA",
        "primary_color": "#0f3d2e",
        "secondary_color": "#c5a642",
    },
    {
        "name": "Nickel Beach",
        "mascot": "Sea Turtles",
        "team_id": "NICKEL_BEACH",
        "primary_color": "#008b8f",
        "secondary_color": "#2a2a2a",
    },
    {
        "name": "Crickstown",
        "mascot": "Caribou",
        "team_id": "CRICKSTOWN",
        "primary_color": "#6a1f2b",
        "secondary_color": "#f3e6d0",
    },
    {
        "name": "Chapel Hill",
        "mascot": "Sky",
        "team_id": "CHAPEL_HILL",
        "primary_color": "#87b5e6",
        "secondary_color": "#1e2f5b",
    },
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    connection = connect_migration_target("gob-staging", write=args.apply)
    db_name = "gob-staging"
    teams = connection.database["teams"]
    for t in NEW_TEAMS:
        existing = teams.find_one({"$or": [{"name": t["name"]}, {"team_id": t["team_id"]}]})
        if existing:
            print(f"  [{db_name}] ⏭️  Skip {t['name']} (already exists)")
            continue
        doc = {
            "name": t["name"],
            "mascot": t["mascot"],
            "team_id": t["team_id"],
            "primary_color": t["primary_color"],
            "secondary_color": t["secondary_color"],
            "player_ids": [],
            **TEAM_ATTRS_ZERO,
        }
        if args.apply:
            teams.insert_one(doc)
        print(f"  [{db_name}] ✅ {'Inserted' if args.apply else 'Would insert'} {t['name']} ({t['team_id']})")
    print("\n✅ Done.")
    connection.close()


if __name__ == "__main__":
    main()
