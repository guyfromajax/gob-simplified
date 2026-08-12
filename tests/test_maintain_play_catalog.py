from __future__ import annotations

import mongomock

from scripts.maintain_play_catalog import remove_universal_stats


def test_remove_universal_stats_is_dry_run_first_and_narrow():
    plays = mongomock.MongoClient().catalog.plays
    plays.insert_many([
        {"name": "Legacy", "game_stats": {"times_run": 2}, "season_stats": {}},
        {"name": "Current", "effectiveness": 7},
    ])
    plan = remove_universal_stats(plays, apply=False)
    assert plan == {"game_stats": 1, "season_stats": 1, "documents": 1}
    assert "game_stats" in plays.find_one({"name": "Legacy"})

    remove_universal_stats(plays, apply=True)
    legacy = plays.find_one({"name": "Legacy"})
    assert "game_stats" not in legacy
    assert "season_stats" not in legacy
    assert plays.find_one({"name": "Current"})["effectiveness"] == 7
