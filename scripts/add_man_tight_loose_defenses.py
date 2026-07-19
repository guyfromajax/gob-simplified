"""
Add the two new first-class man defenses — Deny Man (`man-tight`) and Loose Man (`man-loose`) — to
`defenses_collection` (integrating_new_d_plays.md, Phase 1.1).

Mirrors `add_base_man_defense.py` exactly: **additive UPSERT by `defense_id`** — inserts if missing,
updates only descriptive fields if present, and NEVER deletes/replaces existing docs or stats
(`$setOnInsert` preserves any accumulated game/season stats). Safe to re-run (idempotent).

Run STAGING FIRST (point MONGO_DB_NAME at gob-staging), verify, then prod:
    MONGO_DB_NAME=gob-staging python scripts/add_man_tight_loose_defenses.py

Naming (locked, integrating_new_d_plays.md §0):
  defense_id `man-tight`  → display "Deny Man"   (renamed from legacy `man_pressure`)
  defense_id `man-loose`  → display "Loose Man"
Both are Man-type (is_zone = False); posture derives from the id (man-tight→tight, man-loose→loose).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from BackEnd.db import defenses_collection


def _create_granular_stats():
    return {
        "used": 0,
        "success": 0,
        "vs_motion": {"attempts": 0, "success": 0},
        "vs_set": {"attempts": 0, "success": 0},
        "vs_inside": {"attempts": 0, "success": 0},
        "vs_attack": {"attempts": 0, "success": 0},
        "vs_outside": {"attempts": 0, "success": 0},
        "vs_motion_inside": {"attempts": 0, "success": 0},
        "vs_motion_attack": {"attempts": 0, "success": 0},
        "vs_motion_outside": {"attempts": 0, "success": 0},
        "vs_set_inside": {"attempts": 0, "success": 0},
        "vs_set_attack": {"attempts": 0, "success": 0},
        "vs_set_outside": {"attempts": 0, "success": 0},
    }


_NEW_DEFENSES = [
    {
        "defense_id": "man-tight",
        "defense_type": "Man",
        "name": "Deny Man",
        "description": "Tight/deny man defense — pressures on-ball and denies passing lanes.",
        "effectiveness": 0,
        "cloaking": 0,
        "game_stats": _create_granular_stats(),
        "season_stats": _create_granular_stats(),
        "zone_definitions": None,
        "shift_triggers": None,
    },
    {
        "defense_id": "man-loose",
        "defense_type": "Man",
        "name": "Loose Man",
        "description": "Loose/sagging man defense — extra cushion, help toward the ball line.",
        "effectiveness": 0,
        "cloaking": 0,
        "game_stats": _create_granular_stats(),
        "season_stats": _create_granular_stats(),
        "zone_definitions": None,
        "shift_triggers": None,
    },
]


def add_man_tight_loose_defenses():
    for defense in _NEW_DEFENSES:
        did = defense["defense_id"]
        existing = defenses_collection.find_one({"defense_id": did})
        if existing:
            print(f"  ⚠️  '{defense['name']}' ({did}) already exists — updating descriptive fields only (stats preserved).")
            defenses_collection.update_one(
                {"defense_id": did},
                {
                    "$set": {
                        "name": defense["name"],
                        "description": defense["description"],
                        "defense_type": defense["defense_type"],
                        "effectiveness": defense["effectiveness"],
                        "cloaking": defense["cloaking"],
                        "zone_definitions": defense["zone_definitions"],
                        "shift_triggers": defense["shift_triggers"],
                    },
                    "$setOnInsert": {
                        "game_stats": defense["game_stats"],
                        "season_stats": defense["season_stats"],
                    },
                },
            )
            print(f"  ✅ Updated: {defense['name']} ({did})")
        else:
            defenses_collection.insert_one(defense)
            print(f"  ✅ Inserted: {defense['name']} ({did})")

        doc = defenses_collection.find_one({"defense_id": did})
        ok = bool(doc) and doc.get("defense_type") == "Man"
        print(f"     verify: id={doc.get('defense_id')} name={doc.get('name')!r} type={doc.get('defense_type')} → {'OK' if ok else 'FAILED'}")


if __name__ == "__main__":
    print(f"Target DB: {os.environ.get('MONGO_DB_NAME', '(default)')} — seeding man-tight / man-loose (additive)...")
    add_man_tight_loose_defenses()
