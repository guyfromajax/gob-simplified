from __future__ import annotations

import mongomock

from scripts.publish_defenses import publish_definitions, repair_missing_baselines


def test_additive_publish_preserves_existing_counters_and_initializes_new_ones():
    client = mongomock.MongoClient()
    staging = client.staging.defenses
    production = client.production.defenses
    staging.insert_many([
        {"defense_id": "man", "name": "Man", "effectiveness": 7,
         "game_stats": {"used": 0}, "season_stats": {"used": 0}},
        {"defense_id": "zone", "name": "Zone", "effectiveness": 3,
         "game_stats": {"used": 0}, "season_stats": {"used": 0}},
    ])
    production.insert_one({
        "defense_id": "man", "name": "Old Man", "effectiveness": 1,
        "game_stats": {"used": 9}, "season_stats": {"used": 21},
    })

    plan = publish_definitions(staging, production, apply=False)
    assert plan == {"insert": 1, "update": 1, "unchanged": 0}
    assert production.find_one({"defense_id": "man"})["name"] == "Old Man"

    publish_definitions(staging, production, apply=True)
    man = production.find_one({"defense_id": "man"})
    zone = production.find_one({"defense_id": "zone"})
    assert man["name"] == "Man"
    assert man["game_stats"] == {"used": 9}
    assert man["season_stats"] == {"used": 21}
    assert zone["game_stats"] == {"used": 0}
    assert zone["season_stats"] == {"used": 0}


def test_baseline_repair_adds_only_missing_fields_and_preserves_existing_values():
    client = mongomock.MongoClient()
    defenses = client.catalog.defenses
    defenses.insert_many([
        {"defense_id": "man-tight", "effectiveness": 7, "cloaking": 3},
        {"defense_id": "zone", "effectiveness": 4, "momentum": 8, "cloaking": 2},
    ])

    plan = repair_missing_baselines(defenses, apply=False)
    assert plan == {"effectiveness": 0, "momentum": 1, "cloaking": 0, "documents": 1}
    assert "momentum" not in defenses.find_one({"defense_id": "man-tight"})

    repair_missing_baselines(defenses, apply=True)
    repaired = defenses.find_one({"defense_id": "man-tight"})
    untouched = defenses.find_one({"defense_id": "zone"})
    assert repaired["momentum"] == 0
    assert repaired["effectiveness"] == 7
    assert repaired["cloaking"] == 3
    assert untouched["momentum"] == 8
