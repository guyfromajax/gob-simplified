from __future__ import annotations

import mongomock

from scripts.maintain_universal_roster import rebuild_roster_ids, recalculate_ratings


def test_roster_maintenance_dry_run_and_apply_share_the_same_plan():
    db = mongomock.MongoClient().db
    team_id = db.teams.insert_one({"name": "Example", "player_ids": []}).inserted_id
    db.players.insert_one({
        "_id": "p1", "team": "Example", "height": 75,
        "attributes": {key: 5 for key in ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT")},
    })

    assert rebuild_roster_ids(db.players, db.teams, apply=False)["changed"] == 1
    assert db.teams.find_one({"_id": team_id})["player_ids"] == []
    assert rebuild_roster_ids(db.players, db.teams, apply=True)["changed"] == 1
    assert db.teams.find_one({"_id": team_id})["player_ids"] == ["p1"]

    assert recalculate_ratings(db.players, apply=False)["changed"] == 1
    assert "position_ratings" not in db.players.find_one({"_id": "p1"})
    assert recalculate_ratings(db.players, apply=True)["changed"] == 1
    assert set(db.players.find_one({"_id": "p1"})["position_ratings"]) == {"PG", "SG", "SF", "PF", "C"}
