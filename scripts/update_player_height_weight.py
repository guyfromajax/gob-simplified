# scripts/update_player_height_weight.py
import os, sys, json
from pathlib import Path

# Make BackEnd importable (same pattern as your ids script)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from BackEnd.db import players_collection  # uses your existing DB setup

TEAMS_DIR = Path(__file__).resolve().parent.parent / "teams"

if not TEAMS_DIR.exists():
    raise SystemExit(f"Teams folder not found: {TEAMS_DIR}")

total = matched = updated = missed = 0

for fp in sorted(TEAMS_DIR.glob("*.json")):
    data = json.loads(fp.read_text(encoding="utf-8"))
    team = data.get("name")
    for p in data.get("players", []):
        total += 1
        h = p.get("height")
        w = p.get("weight")
        if h is None and w is None:
            continue  # nothing to set

        # primary match: team + first_name + last_name
        filt = {"team": team, "first_name": p.get("first_name"), "last_name": p.get("last_name")}
        to_set = {k: v for k, v in {"height": h, "weight": w}.items() if v is not None}

        res = players_collection.update_one(filt, {"$set": to_set})
        if res.matched_count == 0:
            # tiny fallback: try team + jersey if names changed
            jersey = p.get("jersey")
            if jersey is not None:
                res = players_collection.update_one({"team": team, "jersey": jersey}, {"$set": to_set})

        if res.matched_count == 0:
            missed += 1
            print(f"MISS: {team} — {p.get('first_name')} {p.get('last_name')} (jersey {p.get('jersey')})")
        else:
            matched += 1
            if res.modified_count:
                updated += 1
                print(f"SET:  {team} — {p.get('first_name')} {p.get('last_name')} -> {to_set}")
            else:
                print(f"OK:   {team} — {p.get('first_name')} {p.get('last_name')} (no change)")

print("\n— done —")
print(f"players scanned: {total}  matched: {matched}  updated: {updated}  not found: {missed}")
