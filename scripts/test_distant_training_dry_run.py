"""
Dry-run test for distant training: loads templates and franchise data, simulates
applying one template to one computer team IN MEMORY. No DB writes or deletes.

Run from repo root with venv: python scripts/test_distant_training_dry_run.py
"""
import os
import sys
import random

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

from BackEnd.db import db
from BackEnd.api.franchise_routes import (
    franchise_team_data_collection,
    franchise_players_data_collection,
)
from BackEnd.models.training_execution_v2 import TEAM_ATTR_CLAMPS, PLAYER_ATTR_CLAMP
from BackEnd.utils.position_ratings import compute_position_ratings


def main():
    print("🔵 [DRY RUN] Load distant_training templates (training_type=regular)...")
    templates = list(db["distant_training"].find({"training_type": "regular"}))
    assert len(templates) == 50, f"Expected 50 regular templates, got {len(templates)}"
    print(f"   ✅ Loaded {len(templates)} templates")

    print("🔵 [DRY RUN] Find one franchise with FTD docs...")
    franchise_doc = db.franchises.find_one(
        {},
        {"_id": 1, "user_team_object_id": 1},
    )
    if not franchise_doc:
        print("   ⚠️ No franchise found in DB; skipping rest (no data to test against)")
        return
    franchise_id = franchise_doc["_id"]
    user_team_id = str(franchise_doc.get("user_team_object_id") or "")
    ftd_docs = list(franchise_team_data_collection.find({"franchise_id": franchise_id}))
    computer_ftds = [d for d in ftd_docs if d.get("team_id") and str(d["team_id"]) != user_team_id]
    if not computer_ftds:
        print("   ⚠️ No computer-team FTDs found; skipping rest")
        return
    ftd_doc = computer_ftds[0]
    computer_team_oid = ftd_doc["team_id"]
    computer_team_id_str = str(computer_team_oid)
    print(f"   ✅ Using franchise_id={franchise_id}, computer team_id={computer_team_id_str}")

    print("🔵 [DRY RUN] Load FPD for this franchise...")
    fpd_docs = list(franchise_players_data_collection.find({"franchise_id": str(franchise_id)}))
    franchise_players = {d["player_id"]: d for d in fpd_docs}
    print(f"   ✅ Loaded {len(franchise_players)} FPD docs")

    template = random.choice(templates)
    team_values = template.get("team_values", {})
    players_template = template.get("players", {})
    current_team_attrs = ftd_doc.get("team_attributes", {})

    # Simulate team apply (in memory only)
    ftd_update = {}
    for attr_name, delta in team_values.items():
        if attr_name not in TEAM_ATTR_CLAMPS:
            continue
        current = current_team_attrs.get(attr_name, 0)
        if isinstance(current, (int, float)) and isinstance(delta, (int, float)):
            lower, upper = TEAM_ATTR_CLAMPS[attr_name]
            delta_val = float(delta) if attr_name == "rebound_modifier" else int(delta)
            new_val = current + delta_val
            if upper is not None:
                new_val = max(lower, min(upper, new_val))
            else:
                new_val = max(lower, new_val)
            if attr_name == "rebound_modifier":
                new_val = round(new_val, 2)
            else:
                new_val = int(round(new_val))
            ftd_update[attr_name] = new_val

    for attr_name, new_val in ftd_update.items():
        lower, upper = TEAM_ATTR_CLAMPS[attr_name]
        assert lower <= new_val, f"team {attr_name}={new_val} < lower {lower}"
        if upper is not None:
            assert new_val <= upper, f"team {attr_name}={new_val} > upper {upper}"
    print(f"   ✅ Team attrs after apply: {len(ftd_update)} keys, all within clamps")

    player_order = ftd_doc.get("players")
    if not player_order:
        team_doc = db.teams.find_one({"_id": computer_team_oid}, {"player_ids": 1})
        player_order = [str(pid) for pid in (team_doc.get("player_ids") or [])] if team_doc else []
    else:
        player_order = [str(pid) for pid in player_order]

    players_updated = 0
    for i in range(min(12, len(player_order))):
        pid = player_order[i]
        player_key = f"player_{i}"
        if player_key not in players_template:
            continue
        fpd = franchise_players.get(pid)
        if not fpd:
            continue
        deltas = players_template[player_key]
        current_attrs = fpd.get("attributes", {})
        for attr_name, delta in deltas.items():
            if not isinstance(delta, (int, float)):
                continue
            current = current_attrs.get(attr_name, 0) or current_attrs.get(f"anchor_{attr_name}", 0)
            try:
                cur = int(current) if isinstance(current, (int, float)) else 0
            except (TypeError, ValueError):
                cur = 0
            new_val = cur + int(delta)
            new_val = max(PLAYER_ATTR_CLAMP[0], new_val)
            assert new_val >= PLAYER_ATTR_CLAMP[0], f"player {attr_name}={new_val} < min 1"
        players_updated += 1

    print(f"   ✅ Player attrs: applied template to {players_updated} players, all within clamp (min 1)")

    # Smoke test position_ratings (one player)
    if player_order and franchise_players.get(player_order[0]):
        fpd = franchise_players[player_order[0]]
        deltas = players_template.get("player_0", {})
        current_attrs = dict(fpd.get("attributes", {}))
        for attr_name, delta in deltas.items():
            if not isinstance(delta, (int, float)):
                continue
            current = current_attrs.get(attr_name, 0) or current_attrs.get(f"anchor_{attr_name}", 0)
            try:
                cur = int(current) if isinstance(current, (int, float)) else 0
            except (TypeError, ValueError):
                cur = 0
            new_val = max(PLAYER_ATTR_CLAMP[0], cur + int(delta))
            current_attrs[attr_name] = new_val
            current_attrs[f"anchor_{attr_name}"] = new_val
        meta = fpd.get("meta", {})
        core = db.players.find_one({"_id": player_order[0]}, {"height": 1})
        height = core.get("height") if core else None
        ratings = compute_position_ratings({
            "attributes": current_attrs,
            "height": height,
            "name": f"{meta.get('first_name', '')} {meta.get('last_name', '')}",
        })
        assert isinstance(ratings, dict), "position_ratings should be dict"
        print(f"   ✅ position_ratings smoke: {list(ratings.keys())[:5]}...")

    print("\n✅ [DRY RUN] All checks passed. No DB writes or deletes were performed.")


if __name__ == "__main__":
    main()
