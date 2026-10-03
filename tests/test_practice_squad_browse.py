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


# ── The standard team page for a practice squad ──────────────────────────────

def _ps_state():
    return {
        "teams": {
            "ps_A_3": {"display_name": "Region A Varsity", "tier": 3, "region": "A"},
            "ps_B_3": {"display_name": "Region B Varsity", "tier": 3, "region": "B"},
            "ps_C_3": {"display_name": "Region C Varsity", "tier": 3, "region": "C"},
            "ps_C_6": {"display_name": "Region C Scrubs", "tier": 6, "region": "C"},
        },
        "standings": {
            "3": {
                "ps_A_3": {"w": 2, "l": 0},
                "ps_C_3": {"w": 1, "l": 1},
                "ps_B_3": {"w": 0, "l": 2},
            },
        },
        "schedule": {
            "3": [
                {"home_team_id": "ps_B_3", "away_team_id": "ps_C_3", "tier": 3, "week": 3,
                 "status": "completed", "game_id": "g3", "home_score": 64, "away_score": 55},
            ],
            "2": [
                {"home_team_id": "ps_C_3", "away_team_id": "ps_A_3", "tier": 3, "week": 2,
                 "status": "completed", "game_id": "g2", "home_score": 70, "away_score": 61},
                {"home_team_id": "ps_A_3", "away_team_id": "ps_B_3", "tier": 3, "week": 2,
                 "status": "completed", "game_id": "gx", "home_score": 80, "away_score": 60},
            ],
            "4": [
                {"home_team_id": "ps_C_3", "away_team_id": "ps_B_3", "tier": 3, "week": 4,
                 "status": "forfeit", "game_id": None, "home_score": 0, "away_score": 0, "winner": "ps_C_3"},
            ],
            "5": [
                {"home_team_id": "ps_A_3", "away_team_id": "ps_C_3", "tier": 3, "week": 5,
                 "status": "skipped", "game_id": None, "home_score": None, "away_score": None},
            ],
            "9": [
                {"home_team_id": "ps_C_3", "away_team_id": "ps_A_3", "tier": 3, "week": 9,
                 "status": "scheduled", "game_id": None, "home_score": None, "away_score": None},
            ],
        },
    }


def test_team_page_is_the_squad_in_the_team_pages_shape():
    from BackEnd.practice_squad.browse import team_page

    page = team_page(_ps_state(), "ps_C_3")
    assert page["team_id"] == "ps_C_3"
    assert page["name"] == "Region C Varsity"
    assert page["practice_squad"] is True
    assert (page["tier"], page["tier_label"], page["region"]) == (3, "Varsity", "C")
    assert page["record"] == {"wins": 1, "losses": 1}
    # Same order as the standings table: wins, then fewest losses.
    assert page["tier_place"] == "2nd of 3"
    # Results in week order, from this squad's side, whatever side it played on.
    assert [(r["week"], r["site"], r["opponent_name"], r["team_score"], r["opp_score"], r["result"], r["game_id"])
            for r in page["results"][:2]] == [
        (2, "home", "Region A Varsity", 70, 61, "W", "g2"),
        (3, "away", "Region B Varsity", 55, 64, "L", "g3"),
    ]
    # A forfeit is a result with the winner's letter and no box score; a skipped game is nothing.
    forfeit = page["results"][2]
    assert (forfeit["week"], forfeit["result"], forfeit["forfeit"], forfeit["game_id"]) == (4, "W", True, None)
    assert len(page["results"]) == 3
    assert [(u["week"], u["site"], u["opponent_id"]) for u in page["upcoming"]] == [(9, "home", "ps_A_3")]
    assert page["next_game"] == page["upcoming"][0]
    # Nothing a squad does not have.
    for key in ("natl_rank", "conference", "conference_place", "streak"):
        assert key not in page


def test_team_page_adds_completed_tournament_games_and_survives_an_empty_squad():
    from BackEnd.practice_squad.browse import team_page

    extra = [{"home_team_id": "ps_A_3", "away_team_id": "ps_C_3", "home_score": 50, "away_score": 58,
              "game_id": "t16", "status": "completed", "week": 16},
             {"home_team_id": "ps_A_3", "away_team_id": "ps_B_3", "home_score": 50, "away_score": 58,
              "game_id": "other", "status": "completed", "week": 16}]
    page = team_page(_ps_state(), "ps_C_3", extra)
    assert [(r["week"], r["result"], r["game_id"]) for r in page["results"]][-1] == (16, "W", "t16")
    assert "other" not in [r["game_id"] for r in page["results"]]

    # Scrubs sit off the standings table: a record of 0-0 and no place, not an error.
    scrubs = team_page(_ps_state(), "ps_C_6")
    assert scrubs["record"] == {"wins": 0, "losses": 0}
    assert scrubs["tier_place"] is None
    assert scrubs["results"] == [] and scrubs["upcoming"] == [] and scrubs["next_game"] is None
    assert team_page(None, "ps_X_1")["name"] == "ps_X_1"


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_team_route_sends_the_page_and_roster_rows_the_team_page_reads(kind, tmp_path, monkeypatch):
    if kind == "mongo":
        env = _mongomock_env(tmp_path)
    else:
        env = _mongomock_env(
            tmp_path,
            GOB_PERSISTENCE="sqlite",
            GOB_SQLITE_PATH=str(tmp_path / "ps-team.sqlite"),
        )
    store = create_store(env)
    franchise_id = _seed(store)
    fid = str(franchise_id)
    ps = store.franchises_collection.find_one({"_id": franchise_id})["practice_squad"]
    ps["ps_season_stats_backfilled"] = True
    ps["teams"]["ps_C_1"] = {
        "display_name": "Region C All-Americans", "tier": 1, "region": "C",
        "roster": [{"player_id": "p-1", "source": "fpd", "name": "Casey Lane"},
                   {"player_id": "r-1", "source": "frd", "name": "Drew Park"}],
    }
    store.franchises_collection.update_one({"_id": franchise_id}, {"$set": {"practice_squad": ps}})
    store.franchise_players_data_collection.insert_one({
        "franchise_id": fid, "player_id": "p-1",
        "meta": {"first_name": "Casey", "last_name": "Lane", "year": 1, "height": 76, "weight": 190},
        "position_ratings": {"PG": 61, "SF": 70, "C": 50},
        "attributes": {"SC": 50, "CH": 77},
        "ps_season_stats": {"GP": 2, "PTS": 30, "FGM": 10, "FGA": 20},
    })
    store.franchise_recruits_data_collection.insert_one({
        "franchise_id": fid, "recruit_id": "r-1", "name": "Drew Park",
        "position_ratings": {"PG": 66}, "attributes": {"SC": 40},
    })

    import BackEnd.api.franchise_routes as routes
    import BackEnd.utils.ownership as ownership

    monkeypatch.setattr(routes, "db", store.db)
    monkeypatch.setattr(ownership, "franchises_collection", store.franchises_collection)
    monkeypatch.setattr(routes, "franchise_players_data_collection", store.franchise_players_data_collection)
    monkeypatch.setattr(routes, "franchise_recruits_data_collection", store.franchise_recruits_data_collection)
    monkeypatch.setattr(routes, "_format_team_name_map", lambda **_kwargs: {})

    body = routes.get_practice_squad_team(fid, ps_team_id="ps_C_1", user={"user_id": "coach-1"})
    page = body["page"]
    assert page["name"] == "Region C All-Americans"
    assert page["record"] == {"wins": 3, "losses": 1}
    assert page["tier_place"] == "2nd of 5"
    assert [(u["week"], u["site"], u["opponent_name"]) for u in page["upcoming"]] == [
        (8, "home", "Region A All-Americans"),
    ]
    signed, recruit = body["players"]
    # The roster grid's fields, and the season line in the Player Stats shape.
    slots = {str(row["player_id"]): row["position"] for row in body["projected_starting_five"]}
    assert (signed["rt"], signed["source"]) == (70, "fpd")
    # A starter reads at the slot he starts at; anyone else at his best position.
    assert signed["position"] == slots.get("p-1", "SF")
    # The projected five are the page's Starters, in slot order.
    five = [str(row["player_id"]) for row in body["projected_starting_five"]]
    assert five and all(p["starter"] == (p["player_id"] in five) for p in body["players"])
    assert [p["lineup_order"] for p in body["players"] if p["starter"]] == [
        five.index(p["player_id"]) for p in body["players"] if p["starter"]
    ]
    assert signed["totals"]["GP"] == 2 and signed["per_game"]["PTS"] == 15
    assert signed["rates"]["fg_pct"] == 50
    assert (recruit["rt"], recruit["source"]) == (66, "frd")
    assert recruit["position"] == slots.get("r-1", "PG")
    assert recruit["totals"]["GP"] == 0 and recruit["per_game"]["PTS"] is None
    # The keys the old page read are still there.
    assert set(body) >= {"team", "players", "projected_starting_five", "page"}


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_team_route_starters_are_the_full_five_whatever_the_season_fouls(kind, tmp_path, monkeypatch):
    """Season fouls are not fouls in a game: the projected five is five, PG to C.

    The selector reads a flat ``stats`` dict as the current game's line, so a squad whose
    players had five or more SEASON fouls came back with two or three starters.
    """
    if kind == "mongo":
        env = _mongomock_env(tmp_path)
    else:
        env = _mongomock_env(
            tmp_path,
            GOB_PERSISTENCE="sqlite",
            GOB_SQLITE_PATH=str(tmp_path / "ps-five.sqlite"),
        )
    store = create_store(env)
    franchise_id = _seed(store)
    fid = str(franchise_id)
    ps = store.franchises_collection.find_one({"_id": franchise_id})["practice_squad"]
    ps["ps_season_stats_backfilled"] = True
    ids = [f"p-{n:02d}" for n in range(12)]
    ps["teams"]["ps_C_1"] = {
        "display_name": "Region C All-Americans", "tier": 1, "region": "C",
        "roster": [{"player_id": pid, "source": "fpd", "name": f"Player {pid}"} for pid in ids],
    }
    store.franchises_collection.update_one({"_id": franchise_id}, {"$set": {"practice_squad": ps}})
    positions = ["PG", "SG", "SF", "PF", "C"]
    for n, pid in enumerate(ids):
        ratings = {pos: 40 for pos in positions}
        ratings[positions[n % 5]] = 80 - n
        store.franchise_players_data_collection.insert_one({
            "franchise_id": fid, "player_id": pid,
            "meta": {"first_name": "Player", "last_name": pid, "year": 1, "height": 76, "weight": 190},
            "position_ratings": ratings,
            "attributes": {"SC": 50, "NG": 1.0},
            # Ten of the twelve have fouled out of a GAME's worth of fouls over the season.
            "ps_season_stats": {"GP": 6, "PTS": 60, "F": 3 if n in (5, 11) else 9 + n},
        })

    import BackEnd.api.franchise_routes as routes
    import BackEnd.utils.ownership as ownership

    monkeypatch.setattr(routes, "db", store.db)
    monkeypatch.setattr(ownership, "franchises_collection", store.franchises_collection)
    monkeypatch.setattr(routes, "franchise_players_data_collection", store.franchise_players_data_collection)
    monkeypatch.setattr(routes, "franchise_recruits_data_collection", store.franchise_recruits_data_collection)
    monkeypatch.setattr(routes, "_format_team_name_map", lambda **_kwargs: {})

    body = routes.get_practice_squad_team(fid, ps_team_id="ps_C_1", user={"user_id": "coach-1"})
    five = body["projected_starting_five"]
    assert [row["position"] for row in five] == positions
    # The best player at each position, fouls or no fouls.
    assert [row["player_id"] for row in five] == ids[:5]
    starters = [p for p in body["players"] if p["starter"]]
    bench = [p for p in body["players"] if not p["starter"]]
    assert len(body["players"]) == 12 and len(starters) == 5 and len(bench) == 7
    assert sorted(starters, key=lambda p: p["lineup_order"]) == [
        next(p for p in body["players"] if p["player_id"] == pid) for pid in ids[:5]
    ]
    assert [p["lineup_order"] for p in sorted(starters, key=lambda p: p["lineup_order"])] == [0, 1, 2, 3, 4]
    # A starter reads at the position he starts at.
    assert [p["position"] for p in sorted(starters, key=lambda p: p["lineup_order"])] == positions
    assert all(p["lineup_order"] is None for p in bench)
    # The season line itself is still sent, untouched.
    assert body["players"][0]["stats"]["F"] == 9 and body["players"][0]["totals"]["GP"] == 6
