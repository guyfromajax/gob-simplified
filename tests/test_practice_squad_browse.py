"""Practice Squad browse payloads: sorted tiers, win_pct, and the open week.

The blob round-trips through mongomock and SQLite, then the same route
functions read it back.
"""

from bson import ObjectId
import pytest

from BackEnd.persistence import create_store
from BackEnd.practice_squad.browse import ps_open_week, standings_tiers, win_pct
from tests.test_persistence_adapter import _mongomock_env


def _standings_blob():
    return {
        "1": {
            "ps_B_1": {"w": 1, "l": 2},
            "ps_A_1": {"w": 3, "l": 0},
            "ps_C_1": {"w": 3, "l": 1},
            "ps_D_1": {"w": 2, "l": 1},
            "ps_E_1": {"w": 2, "l": 1},
        },
        "6": {"ps_C_6": {"w": 8, "l": 0}},
    }


def _teams_blob():
    return {
        "ps_A_1": {"display_name": "Region A All-Americans"},
        "ps_B_1": {"display_name": "Region B All-Americans"},
        "ps_C_1": {"display_name": "Region C All-Americans"},
        "ps_D_1": {"display_name": "Region D All-Americans"},
        "ps_E_1": {"display_name": "Region E All-Americans"},
        "ps_C_6": {"display_name": "Region C Scrubs"},
    }


def test_win_pct_matches_season_standings_rounding():
    assert win_pct(0, 0) == 0.0
    assert win_pct(3, 0) == 1.0
    assert win_pct(3, 1) == 0.75
    assert win_pct(1, 2) == 0.333


def test_tiers_sort_like_the_page_and_skip_scrubs():
    tiers = standings_tiers(_standings_blob(), _teams_blob(), "C")
    assert [tier["tier"] for tier in tiers] == ["1", "2", "3", "4", "5"]
    assert [tier["label"] for tier in tiers] == [
        "All-Americans", "All-Stars", "Varsity", "JV", "Squad",
    ]
    rows = tiers[0]["rows"]
    assert [row["team_id"] for row in rows] == [
        "ps_A_1", "ps_C_1", "ps_D_1", "ps_E_1", "ps_B_1",
    ]
    assert rows[1]["is_user"] is True
    assert rows[1]["win_pct"] == 0.75
    assert rows[1]["name"] == "Region C All-Americans"
    assert all(row["is_user"] is False for row in rows if row["team_id"] != "ps_C_1")
    assert tiers[1]["rows"] == []


def test_missing_region_marks_no_user_row():
    tiers = standings_tiers(_standings_blob(), _teams_blob(), "")
    assert all(row["is_user"] is False for tier in tiers for row in tier["rows"])


def test_open_week_clamps_to_the_ps_slate():
    assert ps_open_week(1) == 2
    assert ps_open_week(8) == 8
    assert ps_open_week(19) == 19
    assert ps_open_week(27) == 19
    assert ps_open_week(None) == 2


def _seed(store):
    franchise_id = ObjectId()
    team_id = ObjectId()
    store.teams_collection.insert_one({
        "_id": team_id,
        "name": "Lancaster",
        "region": "C",
    })
    store.franchises_collection.insert_one({
        "_id": franchise_id,
        "user_id": "coach-1",
        "user_team_id": "Lancaster",
        "user_team_object_id": str(team_id),
        "week": 8,
        "practice_squad": {
            "initialized": True,
            "standings": _standings_blob(),
            "teams": _teams_blob(),
            "schedule": {
                "8": [{
                    "home_team_id": "ps_C_1",
                    "away_team_id": "ps_A_1",
                    "status": "scheduled",
                }],
            },
        },
    })
    return franchise_id


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_standings_and_schedule_round_trip(kind, tmp_path, monkeypatch):
    if kind == "mongo":
        env = _mongomock_env(tmp_path)
    else:
        env = _mongomock_env(
            tmp_path,
            GOB_PERSISTENCE="sqlite",
            GOB_SQLITE_PATH=str(tmp_path / "ps.sqlite"),
        )
    store = create_store(env)
    franchise_id = _seed(store)
    saved = store.franchises_collection.find_one({"_id": franchise_id})
    assert saved["practice_squad"]["standings"]["1"]["ps_C_1"]["w"] == 3

    import BackEnd.api.franchise_routes as routes
    import BackEnd.utils.ownership as ownership

    monkeypatch.setattr(routes, "db", store.db)
    monkeypatch.setattr(ownership, "franchises_collection", store.franchises_collection)

    standings = routes.get_practice_squad_standings(str(franchise_id), user={"user_id": "coach-1"})
    tier = standings["tiers"][0]
    assert [row["team_id"] for row in tier["rows"]] == [
        "ps_A_1", "ps_C_1", "ps_D_1", "ps_E_1", "ps_B_1",
    ]
    user_row = next(row for row in tier["rows"] if row["is_user"])
    assert user_row["team_id"] == "ps_C_1"
    assert user_row["win_pct"] == 0.75
    assert all(item["tier"] != "6" for item in standings["tiers"])

    schedule = routes.get_practice_squad_schedule(str(franchise_id), user={"user_id": "coach-1"})
    assert schedule["week"] == 8
    assert schedule["current_week"] == 8
    assert 8 in schedule["weeks"]
    assert 16 in schedule["weeks"] and 19 in schedule["weeks"]

    one_week = routes.get_practice_squad_schedule(
        str(franchise_id), week=8, user={"user_id": "coach-1"},
    )
    assert "current_week" not in one_week
    assert one_week["week"] == 8
    assert one_week["games"][0]["home_display"] == "Region C All-Americans"
    assert one_week["games"][0]["away_display"] == "Region A All-Americans"


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_uninitialized_standings_have_no_navy_rows(kind, tmp_path, monkeypatch):
    if kind == "mongo":
        env = _mongomock_env(tmp_path)
    else:
        env = _mongomock_env(
            tmp_path,
            GOB_PERSISTENCE="sqlite",
            GOB_SQLITE_PATH=str(tmp_path / "ps-empty.sqlite"),
        )
    store = create_store(env)
    franchise_id = ObjectId()
    store.franchises_collection.insert_one({
        "_id": franchise_id,
        "user_id": "coach-1",
        "week": 1,
        "practice_squad": {},
    })
    import BackEnd.api.franchise_routes as routes
    import BackEnd.utils.ownership as ownership

    monkeypatch.setattr(routes, "db", store.db)
    monkeypatch.setattr(ownership, "franchises_collection", store.franchises_collection)

    standings = routes.get_practice_squad_standings(str(franchise_id), user={"user_id": "coach-1"})
    assert standings["initialized"] is False
    assert standings["tiers"] == []
    schedule = routes.get_practice_squad_schedule(str(franchise_id), user={"user_id": "coach-1"})
    assert schedule["current_week"] == 2
    assert schedule["weeks"] == []
