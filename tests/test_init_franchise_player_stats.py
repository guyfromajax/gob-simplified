from BackEnd.constants import BOX_SCORE_KEYS
from BackEnd.db import db, players_collection
from BackEnd.utils.stat_updater import init_franchise_player_stats


def setup_db():
    db.franchises.delete_many({})
    players_collection.delete_many({})


def test_init_franchise_player_stats_seeds_zero_blocks():
    setup_db()

    players_collection.insert_many(
        [
            {
                "_id": "p1",
                "first_name": "A",
                "last_name": "One",
                "team": "Team0",
                "stats": {"season": {"PTS": 5}, "career": {"PTS": 10}},
            },
            {
                "_id": "p2",
                "first_name": "B",
                "last_name": "Two",
                "team": "Team1",
                "stats": {"season": {"PTS": 7}, "career": {"PTS": 14}},
            },
        ]
    )

    roster = list(
        players_collection.find({}, {"first_name": 1, "last_name": 1, "team": 1})
    )
    fid = db.franchises.insert_one({}).inserted_id

    init_franchise_player_stats(fid, roster)

    franchise = db.franchises.find_one({"_id": fid}) or {}
    players = franchise.get("players", {})

    assert set(players.keys()) == {"p1", "p2"}
    zero_stats = {k: 0 for k in BOX_SCORE_KEYS}

    for pid, pdata in players.items():
        meta = pdata.get("meta", {})
        assert meta.get("first_name")
        assert meta.get("last_name")
        assert pdata.get("season") == zero_stats
        assert pdata.get("career") == zero_stats

    p1_doc = players_collection.find_one({"_id": "p1"})
    assert p1_doc["stats"]["season"]["PTS"] == 5
    assert p1_doc["stats"]["career"]["PTS"] == 10
