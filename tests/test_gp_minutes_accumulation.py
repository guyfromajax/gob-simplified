"""Season/career GP needs game seconds > 0; season/career MIN is unrounded minutes.

Game box MIN is seconds. Every rollup path converts with seconds / 60 and credits
GP only to rows with MIN > 0.
"""

from bson import ObjectId
from pytest import approx

from BackEnd.db import (
    db,
    franchise_players_data_collection,
    tournaments_collection,
)
from BackEnd.practice_squad.stats import apply_ps_game_stats
from BackEnd.utils import stat_updater
from BackEnd.utils.stat_updater import played_in_game, season_minutes


def _reset():
    db.games.delete_many({})
    db.teams.delete_many({})
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})
    tournaments_collection.delete_many({})


def _row(pid, seconds, pts=0, fga=0):
    return {"playerId": pid, "name": pid, "MIN": seconds, "PTS": pts, "FGA": fga}


def _franchise_setup():
    team_a, team_b = ObjectId(), ObjectId()
    db.teams.insert_many([
        {"_id": team_a, "name": "Lancaster", "team_id": "LANCASTER"},
        {"_id": team_b, "name": "Casino Row", "team_id": "CASINO_ROW"},
    ])
    fid = db.franchises.insert_one({
        "schedule": [[(team_a, team_b)], [(team_b, team_a)]],
        "week": 1,
        "user_team_id": "Lancaster",
        "user_team_object_id": str(team_a),
        "results": {},
        "applied_games": [],
        "applied_matchups": [],
    }).inserted_id
    for pid, team in (("starter", team_a), ("bench", team_a), ("cpu", team_b)):
        franchise_players_data_collection.insert_one({
            "franchise_id": str(fid),
            "player_id": pid,
            "meta": {"first_name": pid, "last_name": "X", "team_id": str(team)},
            "season": {"GP": 0, "MIN": 0, "PTS": 0, "FGA": 0},
            "career": {"GP": 0, "MIN": 0, "PTS": 0, "FGA": 0},
        })
    return fid


def _franchise_game(fid, week, home_box, away_box):
    game_id = str(ObjectId())
    db.games.insert_one({
        "_id": game_id,
        "week": week,
        "quarter": 4,
        "is_final": True,
        "franchise_id": str(fid),
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "teams": {
            "LANCASTER": {"name": "Lancaster", "box_score": away_box},
            "CASINO_ROW": {"name": "Casino Row", "box_score": home_box},
        },
    })
    return game_id


def _fpd(fid, pid):
    return franchise_players_data_collection.find_one(
        {"franchise_id": str(fid), "player_id": pid}, {"_id": 0}
    )


def test_helpers():
    assert played_in_game({"MIN": 1}) is True
    assert played_in_game({"MIN": 0}) is False
    assert played_in_game({}) is False
    assert played_in_game({"MIN": "90"}) is False
    assert season_minutes(839) == approx(13.98333, abs=1e-4)


def test_franchise_zero_second_bench_gets_no_gp_and_1359_is_unrounded():
    _reset()
    fid = _franchise_setup()
    gid = _franchise_game(
        fid, 1,
        {"PG": _row("cpu", 1200, pts=9, fga=7)},
        {"PG": _row("starter", 839, pts=11, fga=8), "B1": _row("bench", 0)},
    )
    stat_updater.finalize_game(gid, mode="franchise", franchise_id=str(fid))

    starter = _fpd(fid, "starter")
    bench = _fpd(fid, "bench")
    for block in ("season", "career"):
        assert starter[block]["GP"] == 1
        assert starter[block]["MIN"] == approx(839 / 60)
        assert starter[block]["MIN"] != 13
        assert starter[block]["PTS"] == 11
        assert bench[block]["GP"] == 0
        assert bench[block]["MIN"] == 0
        assert bench[block]["PTS"] == 0
    assert _fpd(fid, "cpu")["season"]["MIN"] == approx(20.0)


def test_franchise_two_59_second_games_sum_unfloored():
    _reset()
    fid = _franchise_setup()
    g1 = _franchise_game(fid, 1, {"PG": _row("cpu", 2400)}, {"PG": _row("starter", 59)})
    stat_updater.finalize_game(g1, mode="franchise", franchise_id=str(fid))
    db.franchises.update_one({"_id": fid}, {"$set": {"week": 2}})
    g2 = _franchise_game(fid, 2, {"PG": _row("cpu", 2400)}, {"PG": _row("starter", 59)})
    stat_updater.finalize_game(g2, mode="franchise", franchise_id=str(fid))

    season = _fpd(fid, "starter")["season"]
    assert season["GP"] == 2
    assert season["MIN"] == approx(118 / 60)
    assert round(season["MIN"], 2) == 1.97


def test_franchise_refinalize_is_a_no_op():
    _reset()
    fid = _franchise_setup()
    gid = _franchise_game(
        fid, 1,
        {"PG": _row("cpu", 1200, pts=9)},
        {"PG": _row("starter", 839, pts=11), "B1": _row("bench", 0)},
    )
    stat_updater.finalize_game(gid, mode="franchise", franchise_id=str(fid))
    before = {pid: _fpd(fid, pid) for pid in ("starter", "bench", "cpu")}
    stat_updater.finalize_game(gid, mode="franchise", franchise_id=str(fid))
    after = {pid: _fpd(fid, pid) for pid in ("starter", "bench", "cpu")}
    assert after == before


def _tournament_setup():
    db.teams.insert_many([
        {"_id": ObjectId(), "name": "Lancaster", "team_id": "LANCASTER"},
        {"_id": ObjectId(), "name": "Casino Row", "team_id": "CASINO_ROW"},
    ])
    players = {
        pid: {"meta": {"first_name": pid, "team": team}, "season": {"GP": 0, "MIN": 0, "PTS": 0}}
        for pid, team in (("starter", "Lancaster"), ("bench", "Lancaster"), ("cpu", "Casino Row"))
    }
    return tournaments_collection.insert_one({"applied_games": [], "players": players}).inserted_id


def test_tournament_finalize_follows_same_rules_and_is_idempotent():
    _reset()
    tid = _tournament_setup()
    oid = ObjectId()
    gid = str(oid)
    db.games.insert_one({
        "_id": oid,
        "home_team_id": "CASINO_ROW",
        "away_team_id": "LANCASTER",
        "teams": {
            "LANCASTER": {"box_score": {"PG": _row("starter", 839, pts=11), "B1": _row("bench", 0)}},
            "CASINO_ROW": {"box_score": {"PG": _row("cpu", 59, pts=2)}},
        },
    })
    stat_updater.finalize_game(gid, mode="tournament", tournament_id=str(tid))
    players = tournaments_collection.find_one({"_id": tid})["players"]
    assert players["starter"]["season"]["GP"] == 1
    assert players["starter"]["season"]["MIN"] == approx(839 / 60)
    assert players["bench"]["season"]["GP"] == 0
    assert players["bench"]["season"]["MIN"] == 0
    assert players["cpu"]["season"]["MIN"] == approx(59 / 60)

    stat_updater.finalize_game(gid, mode="tournament", tournament_id=str(tid))
    assert tournaments_collection.find_one({"_id": tid})["players"] == players


def test_practice_squad_rollup_follows_same_rules():
    _reset()
    fid = str(ObjectId())
    for pid in ("short", "dnp", "long"):
        franchise_players_data_collection.insert_one({"franchise_id": fid, "player_id": pid})
    gid = str(ObjectId())
    db.games.insert_one({
        "_id": gid,
        "box_score": {
            "T1": {"PG": _row("short", 250, pts=2), "B1": _row("dnp", 0), "SG": _row("long", 839)},
        },
    })
    apply_ps_game_stats(gid, fid, player_sources={"short": "fpd", "dnp": "fpd", "long": "fpd"})

    short = _fpd(fid, "short")["ps_season_stats"]
    assert short["GP"] == 1
    assert short["MIN"] == approx(250 / 60)
    assert "ps_season_stats" not in _fpd(fid, "dnp")
    assert _fpd(fid, "long")["ps_season_stats"]["MIN"] == approx(839 / 60)
