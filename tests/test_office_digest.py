"""Office digest: week snapshot, read-time sections, and the last-game query."""

from bson import ObjectId

from BackEnd.utils.office_digest import (
    LAST_GAME_PROJECTION,
    attitude_counts,
    build_office_digest,
    build_todos,
    capture_office_week_snapshot,
    last_game_match_query,
    merge_office_snapshot,
    office_snapshot_payload,
    resolve_advance_mode,
)


USER = "69a6fcb68d2c56aa82e48a5d"
OPP = "69a6fcb68d2c56aa82e48a5e"


class _Cursor(list):
    def limit(self, _n):
        return self


class _Coll:
    def __init__(self, docs):
        self.docs = docs
        self.calls = 0

    def find(self, _query, _projection=None):
        self.calls += 1
        return list(self.docs)


def _rankings():
    return [
        {"team_id": USER, "W": 12, "L": 4, "natl_rank": 18, "conference": "ACC"},
        {"team_id": OPP, "W": 10, "L": 6, "natl_rank": 40, "conference": "ACC"},
    ]


def _franchise(**extra):
    doc = {
        "_id": "fid",
        "current_season": 1,
        "week": 19,
        "results": {
            "15": [{"away_id": OPP, "home_id": USER, "away_score": 60, "home_score": 70}],
            "16": [{"away_id": USER, "home_id": OPP, "away_score": 71, "home_score": 60}],
            "17": [{"away_id": OPP, "home_id": USER, "away_score": 55, "home_score": 80}],
            "18": [{"away_id": USER, "home_id": OPP, "away_score": 77, "home_score": 66}],
        },
        "office_week_snapshots": {
            "1": {
                "18": {
                    "week": 18,
                    "national_rank_before": 22,
                    "conference_position_before": 3,
                    "team_measures": {"fight": 4, "discipline": 8},
                    "team_measures_before": {"fight": 2, "discipline": 9},
                }
            }
        },
        "latest_training": {},
        "season_news": [{"headline": "Weekly upset report", "kind": "upset"}],
    }
    doc.update(extra)
    return doc


def _ctx(**extra):
    ctx = {
        "franchise_doc": _franchise(),
        "user_team_id": USER,
        "week": 19,
        "national_rank": 18,
        "user_conference": "ACC",
        "chemistry": 18,
        "rankings": _rankings(),
        "em_values": [19, 20, 39, 40, 79, 80],
        "advance_flags": {
            "week": 19,
            "training_completed": True,
            "session_type": "in-season",
        },
        "last_game": {
            "week": 18,
            "away_team_id": USER,
            "home_team_id": OPP,
            "away_score": 77,
            "home_score": 66,
            "away_team_name": "Chapel Hill",
            "home_team_name": "Appalachia",
            "opponent_team_name": "Appalachia",
            "game_id": "g-18",
            "potg": {"name": "Star", "stats": {"pts": 28}},
            "game_doc": {
                "home_team_id": OPP,
                "away_team_id": USER,
                "players": [
                    {"name": "Star", "team": "away", "player_id": "p1", "stats": {"PTS": 28, "REB": 4, "AST": 3}},
                    {"name": "Other", "team": "away", "player_id": "p2", "stats": {"PTS": 10, "REB": 2, "AST": 1}},
                ],
            },
        },
        "next_game": {
            "week": 19,
            "matchup_label": "vs",
            "opponent_team_id": OPP,
            "opponent_team_name": "Appalachia",
            "rank": 40,
            "record": "10-6",
            "opponent_team_conference": "ACC",
            "top_scorer": {"name": "A"},
            "top_rebounder": {"name": "B"},
        },
        "training_report": {
            "player_attribute_display_movements": {
                "p9": {"name": "Fresh Recruit", "SC": {"from": 6, "to": 7}, "SH": {"from": 5, "to": 4}},
                "Legacy Name": {"SC": 1, "SH": -1},
            }
        },
        "recruiting_wire": {
            "counts": {"moved": 2, "dropped": 1},
            "unseen_count": 3,
            "board_saved_week": 18,
            "events": [
                {"kind": "moved_up", "rank": 4, "recruit_id": "r1"},
                {"kind": "dropped_you", "rank": 9, "recruit_id": "r2"},
                {"kind": "displaced", "rank": 2, "recruit_id": "r3"},
            ],
        },
        "recruit_lookup": {
            "r1": {"name": "Ada", "position": "PG", "rt": "A", "lean_rank": 1},
            "r2": {"name": "Bea", "position": "C", "rt": "B", "lean_rank": None},
        },
    }
    ctx.update(extra)
    return ctx


def test_snapshot_merge_is_idempotent_and_skips_after_rank_applied():
    payload = office_snapshot_payload(
        completed_week=5,
        national_rank_before=10,
        conference_position_before=2,
        team_measures={"fight": 3},
        team_measures_before=None,
    )
    franchise = {"_id": "fid", "current_season": 1, "rank_prestige_last_applied_week": 0}
    first = merge_office_snapshot(franchise, 5, payload)
    assert first["1"]["5"]["national_rank_before"] == 10
    franchise["office_week_snapshots"] = first
    assert merge_office_snapshot(franchise, 5, payload) is None

    missing = {"_id": "fid", "current_season": 1, "rank_prestige_last_applied_week": 5}
    assert merge_office_snapshot(missing, 5, payload) is None

    eos = {"_id": "fid", "current_season": 1, "rank_prestige_last_applied_week": 26}
    written = merge_office_snapshot(eos, 27, payload)
    assert written["1"]["27"]["week"] == 5


def test_capture_reads_before_rank_update_and_retry_does_not_rewrite():
    user_oid = ObjectId(USER)
    opp_oid = ObjectId(OPP)
    ftd = _Coll([
        {"team_id": user_oid, "natl_rank": 22, "team_attributes": {"fight": 4, "team_chemistry": 18, "discipline": 1}},
        {"team_id": opp_oid, "natl_rank": 40, "team_attributes": {"fight": 1}},
    ])
    teams = _Coll([
        {"_id": user_oid, "conference": "ACC"},
        {"_id": opp_oid, "conference": "ACC"},
    ])
    franchise = {
        "_id": ObjectId(),
        "current_season": 1,
        "rank_prestige_last_applied_week": 4,
        "results": {
            "4": [{"away_id": str(opp_oid), "home_id": str(user_oid), "away_score": 50, "home_score": 60}],
            "5": [{"away_id": str(user_oid), "home_id": str(opp_oid), "away_score": 70, "home_score": 40}],
        },
    }
    stored = capture_office_week_snapshot(
        franchise, str(user_oid), 5, ftd_collection=ftd, teams_collection=teams
    )
    snap = stored["1"]["5"]
    assert snap["national_rank_before"] == 22
    assert snap["conference_position_before"] == 1
    assert snap["team_measures"]["fight"] == 4
    assert "team_chemistry" not in snap["team_measures"]
    assert "team_measures_before" not in snap
    assert ftd.calls == 1

    franchise["office_week_snapshots"] = stored
    franchise["rank_prestige_last_applied_week"] = 5
    assert capture_office_week_snapshot(
        franchise, str(user_oid), 5, ftd_collection=ftd, teams_collection=teams
    ) is None

    already = {
        "_id": ObjectId(),
        "current_season": 1,
        "rank_prestige_last_applied_week": 5,
        "results": {},
    }
    calls_before = ftd.calls
    assert capture_office_week_snapshot(
        already, str(user_oid), 5, ftd_collection=ftd, teams_collection=teams
    ) is None
    assert ftd.calls == calls_before


def test_snapshot_conference_position_matches_standings_api(monkeypatch):
    """Same wins: point differential decides, not national rank, and the just-completed week is excluded."""
    from BackEnd.api import franchise_routes
    from BackEnd.utils import franchise_team_display as display

    user = ObjectId()
    ahead = ObjectId()
    weak = ObjectId()
    fid = ObjectId()
    before = {
        "1": [{"away_id": str(weak), "home_id": str(user), "away_score": 60, "home_score": 70}],
        "2": [{"away_id": str(weak), "home_id": str(ahead), "away_score": 40, "home_score": 100}],
    }
    franchise = {
        "_id": fid,
        "week": 3,
        "schedule": [],
        "results": before,
        "current_season": 1,
        "rank_prestige_last_applied_week": 0,
    }
    ftd_docs = [
        {"team_id": user, "natl_rank": 5, "team_attributes": {"fight": 1}},
        {"team_id": ahead, "natl_rank": 40, "team_attributes": {}},
        {"team_id": weak, "natl_rank": 80, "team_attributes": {}},
    ]
    team_docs = [
        {"_id": user, "name": "User", "conference": 1, "region": "A"},
        {"_id": ahead, "name": "Ahead", "conference": 1, "region": "A"},
        {"_id": weak, "name": "Weak", "conference": 1, "region": "A"},
    ]

    class _Find:
        def __init__(self, docs):
            self.docs = docs

        def find(self, *_args, **_kwargs):
            return list(self.docs)

        def find_one(self, *_args, **_kwargs):
            return franchise

    monkeypatch.setattr(franchise_routes.db, "franchises", _Find([]))
    monkeypatch.setattr(franchise_routes.db, "teams", _Find(team_docs))
    monkeypatch.setattr(franchise_routes.franchise_team_data_collection, "find", lambda *_a, **_k: list(ftd_docs))
    monkeypatch.setattr(display, "teams_collection", _Find(team_docs))

    payload = franchise_routes.standings(str(fid), profile=False)
    conference = [row for row in payload["standings"] if row.get("conference") == 1]
    api_place = next(index for index, row in enumerate(conference, start=1) if row["team_id"] == str(user))
    assert [row["team_id"] for row in conference] == [str(ahead), str(user), str(weak)]
    assert api_place == 2

    snap_doc = dict(franchise)
    snap_doc["results"] = dict(before)
    snap_doc["results"]["3"] = [{
        "away_id": str(ahead),
        "home_id": str(user),
        "away_score": 50,
        "home_score": 90,
    }]
    stored = capture_office_week_snapshot(
        snap_doc,
        str(user),
        3,
        ftd_collection=_Find(ftd_docs),
        teams_collection=_Find(team_docs),
    )
    assert stored["1"]["3"]["conference_position_before"] == api_place


def test_preseason_first_week_and_signing_day_states():
    preseason = build_office_digest(_ctx(
        franchise_doc={"_id": "fid", "current_season": 1, "week": 1, "results": {}},
        week=1,
        national_rank=8,
        last_game=None,
        advance_flags={"week": 1, "training_completed": False, "session_type": "preseason"},
        newcomers=[{"name": "Walk On", "player_id": "w1"}],
    ))
    assert preseason["state"] == "first_week"
    assert preseason["team_snapshot"]["state"] == "set_after_camp"
    assert preseason["team_snapshot"]["moved_most"] == []
    assert preseason["team_snapshot"]["chemistry"] == {"value": 18, "max": 25}
    assert preseason["season_preview"]["preseason_rank"] == 8
    assert preseason["season_preview"]["team_rt"] is None
    assert preseason["season_preview"]["conference_projection"] is None
    assert preseason["season_preview"]["returning_starters"] is None
    assert preseason["season_preview"]["newcomers"][0]["name"] == "Walk On"
    assert preseason["season_preview"]["opener"]["opponent"] == "Appalachia"
    assert preseason["signing_day"] is None

    ready = build_office_digest(_ctx())
    assert ready["state"] == "win"
    assert ready["team_snapshot"]["state"] == "ready"
    assert ready["what_moved"]["national_rank"] == {"now": 18, "prev": 22, "delta": 4}
    assert ready["what_moved"]["conference_standing"]["now"] == 1
    assert ready["what_moved"]["conference_standing"]["prev"] == 3
    assert ready["what_moved"]["conference_standing"]["delta"] == 2
    assert ready["team_snapshot"]["moved_most"][0] == {"measure": "fight", "value": 4, "delta": 2}

    signing = build_office_digest(_ctx(
        week=35,
        advance_flags={"week": 35, "week_35_orders_submitted": False},
        signing_orders={
            "1": {"id": "r1", "points": 20, "playing_time": True, "scholarship": True},
            "2": {"id": "r2", "points": 10, "playing_time": False},
        },
        signing_points_total=50,
        roster_spots=3,
        last_game=None,
    ))
    assert signing["state"] == "signing_day"
    assert signing["signing_day"]["points_remaining"] == 20
    assert signing["signing_day"]["promises_made"] == 1
    assert signing["signing_day"]["open_roster_spots"] == 3
    assert signing["signing_day"]["targets"][0]["recruit_id"] == "r1"
    assert signing["signing_day"]["targets"][0]["stars"] is None
    assert signing["season_preview"] is None


def test_result_win_uses_potg_and_loss_uses_team_leader():
    won = build_office_digest(_ctx())
    assert won["result"]["user_won"] is True
    assert won["result"]["site"] == "away"
    assert won["result"]["neutral"] is None
    assert won["result"]["opponent_rank"] == 40
    assert won["result"]["leader_role"] == "potg"
    assert won["result"]["leader"]["name"] == "Star"
    assert won["result"]["headline"] is None
    assert won["result"]["box_score"]["path"] == "/box-score.html"
    assert won["result"]["box_score"]["params"]["game_id"] == "g-18"
    assert won["result"]["round_name"] is None

    lost_game = dict(_ctx()["last_game"])
    lost_game["away_score"] = 50
    lost_game["home_score"] = 66
    lost = build_office_digest(_ctx(
        last_game=lost_game,
        franchise_doc=_franchise(season_news=[{"headline": "Chapel Hill falls", "game_id": "g-18"}]),
    ))
    assert lost["state"] == "loss"
    assert lost["result"]["leader_role"] == "team_leader"
    assert lost["result"]["leader"]["name"] == "Star"
    assert lost["result"]["leader"]["stats"]["pts"] == 28
    assert lost["result"]["headline"] == "Chapel Hill falls"


def test_streak_attribute_changes_and_next_game_absences():
    digest = build_office_digest(_ctx())
    assert digest["what_moved"]["record"] == {"wins": 12, "losses": 4}
    assert digest["what_moved"]["streak"] == "W4"
    changes = digest["what_moved"]["attribute_changes"]
    assert changes == [
        {"player_id": "p9", "name": "Fresh Recruit", "attribute": "SC", "from": 6, "to": 7},
        {"player_id": "p9", "name": "Fresh Recruit", "attribute": "SH", "from": 5, "to": 4},
    ]
    assert digest["next_game"]["projected_starting_five"] is None
    assert digest["next_game"]["date"] is None
    assert digest["next_game"]["neutral"] is None
    assert digest["next_game"]["seeds"] is None
    assert digest["next_game"]["stakes"] is None
    assert digest["next_game"]["team_rt"] is None
    assert digest["next_game"]["top_scorer"] == {"name": "A"}
    assert digest["next_game"]["site"] == "home"


def test_attitude_bucket_edges():
    attitude = attitude_counts([19, 20, 39, 40, 59, 60, 79, 80, None, "nope"])
    by_id = {bucket["id"]: bucket["count"] for bucket in attitude["buckets"]}
    assert attitude["player_count"] == 8
    assert by_id == {
        "em_0_19": 1,
        "em_20_39": 2,
        "em_40_59": 2,
        "em_60_79": 2,
        "em_80_plus": 1,
    }


def test_recruiting_wire_and_todos_follow_the_advance_ladder():
    digest = build_office_digest(_ctx())
    wire = digest["recruiting_wire"]
    assert wire["status"] == "2 moved, 1 dropped"
    assert wire["pending_count"] == 0
    assert wire["urgent"] is False
    invite_week = build_office_digest(_ctx(week=22))
    assert invite_week["recruiting_wire"]["pending_count"] == 1
    assert invite_week["recruiting_wire"]["urgent"] is True
    assert wire["unseen_count"] == 3
    assert wire["events"][0]["stars"] is None
    assert wire["events"][0]["filmed_grade"] is None
    assert wire["events"][0]["event_text"] is None
    assert wire["events"][0]["direction"] == "up"
    assert wire["events"][0]["position"] == "PG"
    assert wire["events"][1]["direction"] == "down"
    assert wire["events"][2]["direction"] is None

    flags = {"week": 19, "cut_required": True, "training_completed": False}
    assert resolve_advance_mode(flags) == "cut-players"
    todos = build_todos(flags)
    assert todos[0]["id"] == "assign_practice_squad"
    assert todos[0]["gates_advance"] is True
    assert todos[0]["is_advance_action"] is True
    assert todos[0]["route"] == "/cut-players.html"

    invites = build_todos({"week": 22, "board_saved_week": 21, "training_completed": False})
    assert resolve_advance_mode({"week": 22, "board_saved_week": 21, "training_completed": False}) == "recruit-invites"
    assert invites[0]["id"] == "review_recruit_invites"
    assert invites[0]["done"] is False
    assert invites[0]["is_advance_action"] is True

    trained = build_todos({"week": 19, "training_completed": True, "session_type": "in-season"})
    assert [item["id"] for item in trained] == ["run_training", "play_next_game"]
    assert trained[0]["done"] is True
    assert trained[0]["gates_advance"] is False
    assert trained[1]["is_advance_action"] is True
    assert trained[1]["gates_advance"] is False

    camp = build_todos({"week": 1, "training_completed": False, "session_type": "preseason"})
    assert camp[0]["id"] == "run_training_camp"

    week35 = build_todos({"week": 35, "week_35_orders_submitted": True})
    assert week35[0]["id"] == "run_recruiting_day"
    week36 = build_todos({"week": 36, "week_36_results_seen": False})
    assert week36[0]["id"] == "view_recruiting_results"
    assert week36[0]["is_advance_action"] is True


def test_tournament_state_and_last_game_query_shape():
    semi = dict(_ctx()["last_game"])
    semi["week"] = 28
    tournament = build_office_digest(_ctx(
        week=28,
        last_game=semi,
        advance_flags={
            "week": 28,
            "eos_tournament_active": True,
            "training_disabled_for_postseason": True,
            "user_eliminated": False,
            "has_eos_game_this_week": True,
        },
    ))
    assert tournament["state"] == "tournament"
    assert tournament["result"]["round_name"] == "Conference Tourney Semifinals"
    assert tournament["todos"][0]["id"] == "play_next_game"

    away = ObjectId(USER)
    home = ObjectId(OPP)
    query = last_game_match_query("fid", 18, str(away), str(home))
    assert query["week"] == 18
    assert query["franchise_id"] == "fid"
    pairs = {(row["team1_id"], row["team2_id"]) for row in query["$or"]}
    assert (away, home) in pairs
    assert (home, away) in pairs
    assert (str(away), str(home)) in pairs
    assert "turns" not in LAST_GAME_PROJECTION
    assert "players" in LAST_GAME_PROJECTION


def test_last_completed_game_is_one_projected_query(monkeypatch):
    from BackEnd.api import franchise_routes

    calls = []

    def find(query, projection=None):
        calls.append((query, projection))
        return _Cursor([{
            "_id": "game-1",
            "quarter": 5,
            "is_final": True,
            "players": [{"name": "Star"}],
        }])

    monkeypatch.setattr(franchise_routes.db.games, "find", find)
    found = franchise_routes._find_user_last_completed_game(
        {
            "_id": "fid",
            "week": 19,
            "results": {
                "18": [{"away_id": USER, "home_id": OPP, "away_score": 70, "home_score": 60}],
            },
        },
        USER,
    )
    assert len(calls) == 1
    _query, projection = calls[0]
    assert projection is LAST_GAME_PROJECTION
    assert found["game_id"] == "game-1"
    assert found["week"] == 18


def test_conference_standings_and_opponent_place_match_standings_api(monkeypatch):
    """Ties follow standings_display_sort_key and the conference slice of GET /franchise/standings."""
    from BackEnd.api import franchise_routes
    from BackEnd.utils import franchise_team_display as display

    user = ObjectId()
    ahead = ObjectId()
    twin = ObjectId()
    cellar = ObjectId()
    high = ObjectId()
    opp = ObjectId()
    low = ObjectId()
    fid = ObjectId()
    results = {
        "1": [
            {"away_id": str(cellar), "home_id": str(ahead), "away_score": 40, "home_score": 100},
            {"away_id": str(low), "home_id": str(high), "away_score": 50, "home_score": 80},
        ],
        "2": [
            {"away_id": str(cellar), "home_id": str(user), "away_score": 60, "home_score": 70},
            {"away_id": str(low), "home_id": str(opp), "away_score": 55, "home_score": 60},
        ],
        "3": [
            {"away_id": str(cellar), "home_id": str(twin), "away_score": 70, "home_score": 80},
        ],
    }
    franchise = {
        "_id": fid,
        "week": 4,
        "schedule": [],
        "results": results,
        "current_season": 1,
    }
    ftd_docs = [
        {"team_id": ahead, "natl_rank": 10},
        {"team_id": user, "natl_rank": 20},
        {"team_id": twin, "natl_rank": 30},
        {"team_id": cellar, "natl_rank": 40},
        {"team_id": high, "natl_rank": 5},
        {"team_id": opp, "natl_rank": 15},
        {"team_id": low, "natl_rank": 50},
    ]
    team_docs = [
        {"_id": ahead, "name": "Ahead", "conference": 2, "region": "A"},
        {"_id": user, "name": "Lancaster", "conference": 2, "region": "A"},
        {"_id": twin, "name": "Twin", "conference": 2, "region": "A"},
        {"_id": cellar, "name": "Cellar", "conference": 2, "region": "A"},
        {"_id": high, "name": "High", "conference": 3, "region": "B"},
        {"_id": opp, "name": "Crickstown", "conference": 3, "region": "B"},
        {"_id": low, "name": "Low", "conference": 3, "region": "B"},
    ]

    class _Find:
        def __init__(self, docs):
            self.docs = docs

        def find(self, *_args, **_kwargs):
            return list(self.docs)

        def find_one(self, *_args, **_kwargs):
            return franchise

    monkeypatch.setattr(franchise_routes.db, "franchises", _Find([]))
    monkeypatch.setattr(franchise_routes.db, "teams", _Find(team_docs))
    monkeypatch.setattr(franchise_routes.franchise_team_data_collection, "find", lambda *_a, **_k: list(ftd_docs))
    monkeypatch.setattr(display, "teams_collection", _Find(team_docs))

    payload = franchise_routes.standings(str(fid), profile=False)
    conf2 = [row for row in payload["standings"] if row.get("conference") == 2]
    conf3 = [row for row in payload["standings"] if row.get("conference") == 3]
    assert [row["name"] for row in conf2] == ["Ahead", "Lancaster", "Twin", "Cellar"]
    assert [row["name"] for row in conf3] == ["High", "Crickstown", "Low"]

    rankings = []
    for doc in team_docs:
        match = next(row for row in payload["standings"] if row["team_id"] == str(doc["_id"]))
        rankings.append({
            "team_id": match["team_id"],
            "team_name": match["name"],
            "conference": match["conference"],
            "region": match["region"],
            "W": match["W"],
            "L": match["L"],
            "PF": match["PF"],
            "PA": match["PA"],
            "natl_rank": match["natl_rank"],
        })
    digest = build_office_digest({
        "franchise_doc": {"_id": str(fid), "current_season": 1, "week": 4, "results": {}},
        "user_team_id": str(user),
        "week": 4,
        "national_rank": 20,
        "user_conference": 2,
        "chemistry": 20,
        "rankings": rankings,
        "em_values": [],
        "advance_flags": {"week": 4, "training_completed": True, "session_type": "in-season"},
        "last_game": None,
        "next_game": {
            "week": 4,
            "matchup_label": "vs",
            "opponent_team_id": str(opp),
            "opponent_team_name": "Crickstown",
            "rank": 21,
            "record": {"wins": 1, "losses": 0},
            "opponent_team_conference": 3,
        },
    })
    table = digest["conference_standings"]
    assert table["conference"] == 2
    assert table["region"] == "A"
    assert [row["team_id"] for row in table["rows"]] == [row["team_id"] for row in conf2]
    assert [row["position"] for row in table["rows"]] == [1, 2, 3, 4]
    assert table["rows"][1]["is_user"] is True
    assert table["rows"][1]["team_name"] == "Lancaster"
    assert table["rows"][1]["wins"] == 1
    assert table["rows"][1]["losses"] == 0
    assert table["rows"][0]["differential"] > table["rows"][1]["differential"]
    assert table["rows"][1]["wins"] == table["rows"][2]["wins"]
    assert table["rows"][1]["differential"] == table["rows"][2]["differential"]
    opp_place = next(index for index, row in enumerate(conf3, start=1) if row["team_id"] == str(opp))
    assert digest["next_game"]["conference_position"] == opp_place == 2
    assert digest["next_game"]["conference_size"] == len(conf3) == 3

    missing = build_office_digest(_ctx(next_game={
        "week": 19,
        "matchup_label": "vs",
        "opponent_team_name": "Ghost",
        "rank": 21,
    }))
    assert missing["next_game"]["conference_position"] is None
    assert missing["next_game"]["conference_size"] is None
