"""Leaders snapshot: same boards as the live scan, invalidated when season stats change."""

import copy

from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api.franchise_routes import get_leaders
from BackEnd.db import db, franchise_players_data_collection
from BackEnd.persistence import get_store
from BackEnd.utils import leaders_snapshot
from BackEnd.utils.leaders_snapshot import note_season_stats_written, read_snapshot

client = TestClient(app)

CATEGORIES = ["PTS", "3PTM", "AST", "BLK", "FG%", "REB", "STL", "DEF%"]


def setup_function(_fn):
    db.franchises.delete_many({})
    franchise_players_data_collection.delete_many({})
    get_store().leaders_snapshots_collection.delete_many({})


def _games(team_a: str, team_b: str, count: int = 10) -> dict:
    return {
        str(week): [
            {
                "away_id": team_a,
                "home_id": team_b,
                "away_score": 70,
                "home_score": 60,
            }
        ]
        for week in range(1, count + 1)
    }


def _player(fid, player_id, first, last, team, team_id, season, career=None):
    return {
        "franchise_id": str(fid),
        "player_id": player_id,
        "meta": {
            "first_name": first,
            "last_name": last,
            "team": team,
            "team_id": team_id,
        },
        "season": season,
        "career": career or season,
    }


def _seed_two_conferences():
    alpha_id = ObjectId()
    beta_id = ObjectId()
    db.teams.insert_one(
        {"_id": alpha_id, "name": "Alpha College", "conference": "East", "region": "North"}
    )
    db.teams.insert_one(
        {"_id": beta_id, "name": "Beta College", "conference": "West", "region": "South"}
    )
    fid = db.franchises.insert_one(
        {
            "week": 11,
            "current_season": 1,
            "user_team_id": "Alpha College",
            "user_team_object_id": str(alpha_id),
            "results": _games(str(alpha_id), str(beta_id)),
        }
    ).inserted_id
    ann = {
        "GP": 10, "PTS": 100, "REB": 50, "AST": 20, "3PTM": 5, "BLK": 2, "STL": 3,
        "FGM": 40, "FGA": 80, "DEF_S": 30, "DEF_A": 60,
    }
    bea = {
        "GP": 10, "PTS": 100, "REB": 80, "AST": 40, "3PTM": 15, "BLK": 8, "STL": 1,
        "FGM": 50, "FGA": 80, "DEF_S": 48, "DEF_A": 60,
    }
    cal_season = {
        "GP": 10, "PTS": 300, "REB": 20, "AST": 10, "3PTM": 40, "BLK": 1, "STL": 20,
        "FGM": 70, "FGA": 100, "DEF_S": 20, "DEF_A": 80,
    }
    cal_career = {
        "GP": 10, "PTS": 10, "REB": 10, "AST": 10, "3PTM": 1, "BLK": 1, "STL": 1,
        "FGM": 20, "FGA": 50, "DEF_S": 10, "DEF_A": 50,
    }
    franchise_players_data_collection.insert_many(
        [
            _player(fid, "ann", "Ann", "Alpha", "Alpha College", str(alpha_id), ann),
            _player(fid, "bea", "Bea", "Alpha", "Alpha College", str(alpha_id), bea),
            _player(fid, "cal", "Cal", "Beta", "Beta College", str(beta_id), cal_season, cal_career),
            _player(
                fid, "idle", "Ida", "Idle", "Alpha College", str(alpha_id),
                {"GP": 0, "PTS": 99, "3PTM": 0, "BLK": 0, "STL": 0, "FGM": 0, "FGA": 0, "DEF_S": 0, "DEF_A": 0},
            ),
        ]
    )
    return str(fid)


def _board(fid: str, *, scope: str, view_scope: str) -> dict:
    resp = client.get(
        "/franchise/leaders",
        params={"franchise_id": fid, "scope": scope, "limit": 10, "view_scope": view_scope},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _names(board: dict, stat: str) -> list[str]:
    return [row["name"] for row in board[stat]]


def test_snapshot_matches_live_scan_for_every_category():
    fid = _seed_two_conferences()

    live_national = _board(fid, scope="season", view_scope="national")
    snap_national = _board(fid, scope="season", view_scope="national")
    assert snap_national == live_national

    get_store().leaders_snapshots_collection.delete_many({})
    live_conference = _board(fid, scope="season", view_scope="conference")
    snap_conference = _board(fid, scope="season", view_scope="conference")
    assert snap_conference == live_conference

    get_store().leaders_snapshots_collection.delete_many({})
    live_career = _board(fid, scope="career", view_scope="national")
    snap_career = _board(fid, scope="career", view_scope="national")
    assert snap_career == live_career

    for stat in CATEGORIES:
        assert live_national[stat], stat
        assert "conference" in live_national[stat][0]
        assert "region" in live_national[stat][0]

    # Per game (PTS/REB/AST) and raw totals (3PTM/BLK/STL), national and conference.
    assert _names(live_national, "PTS")[0] == "Cal Beta"
    assert live_national["PTS"][0]["value"] == 30.0
    assert live_national["REB"][0]["value"] == 8.0
    assert live_national["AST"][0]["value"] == 4.0
    assert live_national["3PTM"][0] == {
        "player_id": "cal",
        "name": "Cal Beta",
        "team": "Beta College",
        "value": 40,
        "conference": "West",
        "region": "South",
    }
    assert live_national["BLK"][0]["value"] == 8
    assert live_national["STL"][0]["value"] == 20
    assert live_national["FG%"][0]["value"] == 70.0
    assert live_national["DEF%"][0]["value"] == 80
    # Same per-game value and the same point total: insertion order, Ann then Bea.
    assert _names(live_national, "PTS")[1:] == ["Ann Alpha", "Bea Alpha"]

    assert _names(live_conference, "PTS") == ["Ann Alpha", "Bea Alpha"]
    assert "Cal Beta" not in _names(live_conference, "3PTM")
    assert live_conference["3PTM"][0]["value"] == 15

    # Career uses the career block. Cal's season points would lead; his career points do not.
    assert _names(live_career, "PTS")[0] == "Ann Alpha"
    assert live_career["PTS"][0]["value"] == 10.0
    assert _names(live_career, "PTS")[0] != _names(live_national, "PTS")[0]

    east = list(db.teams.find({"conference": "East"}, {"_id": 1, "name": 1}))
    allowed_ids = {str(team["_id"]) for team in east}
    allowed_names = {team.get("name") for team in east if team.get("name")}
    for scope, board, ids, names in (
        ("season", live_national, None, None),
        ("career", live_career, None, None),
        ("season", live_conference, allowed_ids, allowed_names),
    ):
        for stat in CATEGORIES:
            ranked = get_leaders(
                fid,
                scope=scope,
                stat=stat,
                limit=10,
                allowed_team_ids=ids,
                allowed_team_names=names,
            )
            assert [row["player_id"] for row in board[stat]] == [row["player_id"] for row in ranked]
            assert [row["value"] for row in board[stat]] == [row["value"] for row in ranked]


def test_midweek_season_stat_write_is_visible_on_the_next_read():
    fid = _seed_two_conferences()
    before = _board(fid, scope="season", view_scope="national")
    assert before["PTS"][0]["name"] == "Cal Beta"

    franchise_players_data_collection.update_one(
        {"franchise_id": fid, "player_id": "ann"},
        {"$set": {"season.PTS": 1000}},
    )
    note_season_stats_written(fid)

    after = _board(fid, scope="season", view_scope="national")
    assert after["PTS"][0]["name"] == "Ann Alpha"
    assert after["PTS"][0]["value"] == 100.0
    assert after != before


def test_missing_snapshot_uses_the_live_scan():
    fid = db.franchises.insert_one({}).inserted_id
    franchise_players_data_collection.insert_one(
        {
            "franchise_id": str(fid),
            "player_id": "solo",
            "meta": {"first_name": "Solo", "last_name": "Player", "team": "A"},
            "season": {"GP": 2, "PTS": 15, "3PTM": 4},
        }
    )
    assert get_store().leaders_snapshots_collection.find_one({"_id": str(fid)}) is None

    board = _board(str(fid), scope="season", view_scope="national")
    ranked = get_leaders(str(fid), scope="season", stat="PTS", limit=10)
    assert board["PTS"][0]["name"] == "Solo Player"
    assert board["PTS"][0]["value"] == ranked[0]["value"] == 7.5
    assert board["3PTM"][0]["value"] == 4

    stored = get_store().leaders_snapshots_collection.find_one({"_id": str(fid)})
    assert stored is not None
    assert stored.get("stale") is False
    assert stored.get("gen") == 0


def _process_memory() -> dict:
    """Copy any process-local caches so a second process can be simulated."""
    saved = {}
    for name in ("_stale_marked", "_local_gen", "_built_gen"):
        slot = getattr(leaders_snapshot, name, None)
        if isinstance(slot, (set, dict)):
            saved[name] = copy.deepcopy(slot)
    return saved


def _install_process_memory(saved: dict) -> None:
    for name in ("_stale_marked", "_local_gen", "_built_gen"):
        slot = getattr(leaders_snapshot, name, None)
        if isinstance(slot, set):
            slot.clear()
            slot.update(saved.get(name) or ())
        elif isinstance(slot, dict):
            slot.clear()
            slot.update(saved.get(name) or {})


def test_second_process_rebuild_does_not_let_the_writer_skip_the_next_mark():
    """Process A marks, B rebuilds, A writes again. The next read must see the write."""
    fid = _seed_two_conferences()
    note_season_stats_written(fid)
    assert read_snapshot(fid) is None

    before = _board(fid, scope="season", view_scope="national")
    assert before["PTS"][0]["name"] == "Cal Beta"
    assert read_snapshot(fid).get("stale") is False

    note_season_stats_written(fid)
    writer = _process_memory()
    _install_process_memory({})
    rebuilt = _board(fid, scope="season", view_scope="national")
    assert rebuilt["PTS"][0]["name"] == "Cal Beta"
    assert read_snapshot(fid).get("stale") is False

    _install_process_memory(writer)
    franchise_players_data_collection.update_one(
        {"franchise_id": fid, "player_id": "ann"},
        {"$set": {"season.PTS": 1000}},
    )
    note_season_stats_written(fid)
    _install_process_memory({})

    after = _board(fid, scope="season", view_scope="national")
    assert after["PTS"][0]["name"] == "Ann Alpha"
    assert after["PTS"][0]["value"] == 100.0


def test_write_between_load_and_store_is_not_saved(monkeypatch):
    fid = _seed_two_conferences()
    _board(fid, scope="season", view_scope="national")
    note_season_stats_written(fid)
    frozen = read_snapshot(fid)
    assert frozen.get("stale") is True
    frozen_pts = next(row[7] for row in frozen["rows"] if row[0] == "ann")

    real_load = leaders_snapshot.load_lines

    def load_then_write(franchise_id):
        rows = real_load(franchise_id)
        franchise_players_data_collection.update_one(
            {"franchise_id": franchise_id, "player_id": "ann"},
            {"$set": {"season.PTS": 1000}},
        )
        note_season_stats_written(franchise_id)
        return rows

    monkeypatch.setattr(leaders_snapshot, "load_lines", load_then_write)
    during = _board(fid, scope="season", view_scope="national")
    assert during["PTS"][0]["name"] == "Cal Beta"

    held = read_snapshot(fid)
    assert held.get("stale") is True
    assert next(row[7] for row in held["rows"] if row[0] == "ann") == frozen_pts

    monkeypatch.undo()
    after = _board(fid, scope="season", view_scope="national")
    assert after["PTS"][0]["name"] == "Ann Alpha"
    assert after["PTS"][0]["value"] == 100.0
