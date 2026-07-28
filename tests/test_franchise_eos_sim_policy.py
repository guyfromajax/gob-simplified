from bson import ObjectId
from unittest.mock import MagicMock

from BackEnd.api import franchise_routes
from BackEnd.api.franchise_routes import (
    RegionByeModalSeenRequest,
    SimRestOfTournamentRequest,
    _get_user_eos_phase_status,
    _save_user_eos_bracket_result,
    _should_show_region_bye_modal,
    _should_use_tbt_for_eos_game,
    mark_region_bye_modal_seen,
    sim_rest_of_tournament,
)
from BackEnd.tournament import franchise_tournament as ft


def test_all_eos_matchups_use_tbt_regardless_of_user_scope():
    user_scope = {
        "active": True,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(27, {"phase": "conference", "conference": 3}, user_scope) is True
    assert _should_use_tbt_for_eos_game(28, {"phase": "conference", "conference": 4}, user_scope) is True
    assert _should_use_tbt_for_eos_game(29, {"phase": "conference", "conference": 5}, user_scope) is True
    assert _should_use_tbt_for_eos_game(30, {"phase": "region", "region": "B"}, user_scope) is True
    assert _should_use_tbt_for_eos_game(31, {"phase": "region", "region": "C"}, user_scope) is True
    assert _should_use_tbt_for_eos_game(32, {"phase": "national"}, user_scope) is True
    assert _should_use_tbt_for_eos_game(34, {"phase": "national"}, user_scope) is True


def test_all_eos_matchups_use_tbt_when_user_is_not_active():
    user_scope = {
        "active": False,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(28, {"phase": "conference", "conference": 3}, user_scope) is True
    assert _should_use_tbt_for_eos_game(30, {"phase": "region", "region": "B"}, user_scope) is True
    assert _should_use_tbt_for_eos_game(33, {"phase": "national"}, user_scope) is True


def test_user_eos_bracket_result_persists_without_game_id():
    away_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    user_team_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    franchise_doc = {
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {
                            "away_team": away_id,
                            "home_team": user_team_id,
                            "winner": None,
                        }
                    ],
                },
            }
        }
    }
    week_games_meta = [
        {
            "away_id": away_id,
            "home_id": user_team_id,
            "phase": "conference",
            "conference": 1,
            "round": 1,
            "matchup_index": 0,
        }
    ]

    _save_user_eos_bracket_result(
        franchise_doc,
        week_games_meta=week_games_meta,
        user_team_id_str=user_team_id,
        team1_id=away_id,
        team2_id=user_team_id,
        team1_score=61,
        team2_score=72,
        game_id=None,
    )

    matchup = franchise_doc["conference_tournaments"]["1"]["bracket"]["round1"][0]
    assert matchup["winner"] == user_team_id
    assert matchup["score"] == {"home": 72, "away": 61}
    assert matchup["game_id"] == ""


def test_user_eos_bracket_result_persists_user_loss():
    user_team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    opponent_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    franchise_doc = {
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {
                            "away_team": user_team_id,
                            "home_team": opponent_id,
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        }
                    ],
                    "round2": [],
                    "final": [],
                },
            }
        }
    }
    week_games_meta = [
        {
            "away_id": user_team_id,
            "home_id": opponent_id,
            "phase": "conference",
            "conference": 1,
            "round": 1,
            "matchup_index": 0,
        }
    ]

    _save_user_eos_bracket_result(
        franchise_doc,
        week_games_meta=week_games_meta,
        user_team_id_str=user_team_id,
        team1_id=user_team_id,
        team2_id=opponent_id,
        team1_score=61,
        team2_score=72,
        game_id="loss-game",
        week=27,
    )

    matchup = franchise_doc["conference_tournaments"]["1"]["bracket"]["round1"][0]
    assert matchup["winner"] == opponent_id
    assert matchup["game_id"] == "loss-game"
    assert matchup["score"] == {"home": 72, "away": 61}


def test_save_user_eos_bracket_falls_back_to_playable_meta_when_calendar_final_empty():
    """Regression: franchise week 29 + current_round 2 + empty final → calendar meta has no row;
    playable meta (include_completed=False) still lists the open semifinal."""
    uid_user = "eeeeeeeeeeeeeeeeeeeeeeee"
    uid_opp = "ffffffffffffffffffffffff"
    t_a = "aaaaaaaaaaaaaaaaaaaaaaaa"
    t_b = "bbbbbbbbbbbbbbbbbbbbbbbb"
    franchise_doc = {
        "conference_tournaments": {
            "1": {
                "current_round": 2,
                "bracket": {
                    "round1": [
                        {
                            "home_team": t_a,
                            "away_team": t_b,
                            "winner": t_a,
                            "game_id": "g1",
                            "score": {},
                        },
                        {
                            "home_team": t_a,
                            "away_team": t_b,
                            "winner": t_a,
                            "game_id": "g2",
                            "score": {},
                        },
                        {
                            "home_team": t_a,
                            "away_team": t_b,
                            "winner": t_a,
                            "game_id": "g3",
                            "score": {},
                        },
                        {
                            "home_team": t_a,
                            "away_team": t_b,
                            "winner": t_a,
                            "game_id": "g4",
                            "score": {},
                        },
                    ],
                    "round2": [
                        {
                            "home_team": t_a,
                            "away_team": t_b,
                            "winner": t_a,
                            "game_id": "gs0",
                            "score": {},
                        },
                        {
                            "home_team": uid_opp,
                            "away_team": uid_user,
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                    ],
                    "final": [],
                },
                "seeds": {uid_user: 6, uid_opp: 2},
            }
        }
    }
    # Calendar week 29 uses final only — empty bracket.final → no meta rows.
    _save_user_eos_bracket_result(
        franchise_doc,
        week_games_meta=[],
        user_team_id_str=uid_user,
        team1_id=uid_user,
        team2_id=uid_opp,
        team1_score=60,
        team2_score=70,
        game_id="game-semis-fix",
        week=29,
    )
    matchup = franchise_doc["conference_tournaments"]["1"]["bracket"]["round2"][1]
    assert matchup["winner"] == uid_opp
    assert matchup["game_id"] == "game-semis-fix"
    assert matchup["score"] == {"home": 70, "away": 60}


def test_eos_result_row_without_game_doc_syncs_conference_bracket(monkeypatch):
    away_id = ObjectId()
    home_id = ObjectId()
    fid = ObjectId()
    franchise_doc = {
        "_id": fid,
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {
                            "away_team": str(away_id),
                            "home_team": str(home_id),
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        }
                    ],
                    "round2": [],
                    "final": [],
                },
            }
        },
    }
    mock_db = MagicMock()
    mock_db.games.find_one.return_value = None
    monkeypatch.setattr(franchise_routes, "db", mock_db)
    monkeypatch.setattr(franchise_routes, "generate_game_id", lambda: "generated-game-id")

    franchise_routes._sync_eos_bracket_from_result_row(
        franchise_doc,
        row={
            "away_id": str(away_id),
            "home_id": str(home_id),
            "away_score": 55,
            "home_score": 68,
        },
        away_id=away_id,
        home_id=home_id,
        week=27,
        franchise_id_str=str(fid),
        g={
            "phase": "conference",
            "conference": 1,
            "round": 1,
            "matchup_index": 0,
        },
    )

    matchup = franchise_doc["conference_tournaments"]["1"]["bracket"]["round1"][0]
    assert matchup["winner"] == str(home_id)
    assert matchup["game_id"] == "generated-game-id"
    assert matchup["score"] == {"home": 68, "away": 55}
    mock_db.games.update_one.assert_called_once()


def test_region_phase_a_merge_resolves_final_placeholders_from_known_winners():
    user_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    cpu_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    stale_user_side = {
        "A": {
            "round1": [
                {
                    "away_team": user_id,
                    "home_team": "cccccccccccccccccccccccc",
                    "winner": user_id,
                    "game_id": "user-r1",
                    "score": {"away": 71, "home": 60},
                },
                {
                    "away_team": "dddddddddddddddddddddddd",
                    "home_team": "eeeeeeeeeeeeeeeeeeeeeeee",
                    "winner": None,
                    "game_id": None,
                    "score": {},
                },
            ],
            "final": [
                {
                    "away_team": user_id,
                    "home_team": "R1_1",
                    "winner": None,
                    "game_id": None,
                    "score": {},
                }
            ],
        }
    }
    fresh_cpu_side = {
        "A": {
            "round1": [
                {
                    "away_team": user_id,
                    "home_team": "cccccccccccccccccccccccc",
                    "winner": None,
                    "game_id": None,
                    "score": {},
                },
                {
                    "away_team": "dddddddddddddddddddddddd",
                    "home_team": "eeeeeeeeeeeeeeeeeeeeeeee",
                    "winner": cpu_id,
                    "game_id": "cpu-r1",
                    "score": {"away": 53, "home": 54},
                },
            ],
            "final": [
                {
                    "away_team": "R1_0",
                    "home_team": cpu_id,
                    "winner": None,
                    "game_id": None,
                    "score": {},
                }
            ],
        }
    }

    merged = ft.merge_region_tournaments_phase_a(fresh_cpu_side, stale_user_side)
    final = merged["A"]["final"][0]
    assert final["away_team"] == user_id
    assert final["home_team"] == cpu_id


def test_user_can_reenter_in_region_after_conference_loss(monkeypatch):
    user_team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"

    monkeypatch.setattr(
        franchise_routes,
        "_build_user_eos_sim_scope",
        lambda franchise_doc, team_id: {
            "active": False,
            "conference": 3,
            "region": "B",
            "region_conferences": (3, 4),
        },
    )

    franchise_doc = {
        "conference_tournaments": {
            "3": {
                "bracket": {
                    "round1": [
                        {
                            "away_team": user_team_id,
                            "home_team": "bbbbbbbbbbbbbbbbbbbbbbbb",
                            "winner": "bbbbbbbbbbbbbbbbbbbbbbbb",
                        }
                    ],
                    "round2": [],
                    "final": [],
                },
                "current_round": 3,
            },
            "4": {
                "bracket": {
                    "round1": [],
                    "round2": [],
                    "final": [
                        {
                            "away_team": "cccccccccccccccccccccccc",
                            "home_team": "dddddddddddddddddddddddd",
                            "winner": None,
                        }
                    ],
                },
                "current_round": 3,
            },
        },
        "region_tournaments": {
            "B": {
                "round1": [],
                "final": [
                    {
                        "away_team": user_team_id,
                        "home_team": "eeeeeeeeeeeeeeeeeeeeeeee",
                        "winner": None,
                    }
                ],
                "current_round": 1,
            }
        },
    }

    week_29_status = _get_user_eos_phase_status(franchise_doc, user_team_id, 29)
    assert week_29_status["active_this_week"] is False
    assert week_29_status["region_qualified"] is True
    assert week_29_status["eliminated_from_current_phase"] is False

    week_30_status = _get_user_eos_phase_status(franchise_doc, user_team_id, 30)
    # Both conference double-winners wait through week 30 and play the region final in week 31.
    assert week_30_status["active_this_week"] is True
    assert week_30_status["has_game_this_week"] is False
    assert week_30_status["has_bye_this_week"] is True
    assert week_30_status["eliminated_from_current_phase"] is False

    week_31_status = _get_user_eos_phase_status(franchise_doc, user_team_id, 31)
    assert week_31_status["active_this_week"] is True
    assert week_31_status["has_game_this_week"] is True
    assert week_31_status["has_bye_this_week"] is False
    assert week_31_status["eliminated_from_current_phase"] is False


def test_rs1_conf_final_loser_stays_region_eligible(monkeypatch):
    """RS#1 who lost the conf championship must not be treated as season-over before/during region."""
    user_team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    conf_champ_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    other_rs1 = "cccccccccccccccccccccccc"
    cross_conf_champ = "dddddddddddddddddddddddd"

    monkeypatch.setattr(
        franchise_routes,
        "_build_user_eos_sim_scope",
        lambda franchise_doc, team_id: {
            "active": False,
            "conference": 1,
            "region": "A",
            "region_conferences": (1, 2),
        },
    )

    franchise_doc = {
        "conference_tournaments": {
            "1": {
                "champion": conf_champ_id,
                "seeds": {user_team_id: 1, conf_champ_id: 2},
                "bracket": {
                    "round1": [],
                    "round2": [],
                    "final": [
                        {
                            "away_team": user_team_id,
                            "home_team": conf_champ_id,
                            "winner": conf_champ_id,
                        }
                    ],
                },
                "current_round": 3,
            },
            "2": {
                "champion": cross_conf_champ,
                "seeds": {cross_conf_champ: 1, other_rs1: 2},
                "bracket": {"round1": [], "round2": [], "final": []},
                "current_round": 3,
            },
        },
        "region_tournaments": {
            "A": {
                "round1": [
                    {
                        "away_team": conf_champ_id,
                        "home_team": other_rs1,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                    {
                        "away_team": cross_conf_champ,
                        "home_team": user_team_id,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                ],
                "final": [{"away_team": "R1_0", "home_team": "R1_1", "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            }
        },
    }

    week_29 = _get_user_eos_phase_status(franchise_doc, user_team_id, 29)
    assert week_29["region_qualified"] is True
    assert week_29["eliminated_from_current_phase"] is False

    week_30 = _get_user_eos_phase_status(franchise_doc, user_team_id, 30)
    assert week_30["has_game_this_week"] is True
    assert week_30["eliminated_from_current_phase"] is False

    assert ft.user_qualifies_for_region_tournament(franchise_doc, user_team_id, 1) is True
    assert ft.user_qualifies_for_region_tournament(franchise_doc, conf_champ_id, 1) is True


def _region_bye_modal_doc(user_team_id, opponent_id, *, week=30, seen_season=None):
    doc = {
        "_id": ObjectId(),
        "week": week,
        "current_season": 3,
        "eos_tournament_active": True,
        "region_tournaments": {
            "A": {
                "round1": [],
                "final": [
                    {
                        "away_team": user_team_id,
                        "home_team": opponent_id,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    }
                ],
                "current_round": 1,
            }
        },
    }
    if seen_season is not None:
        doc["region_bye_modal_seen_season"] = seen_season
    return doc


def test_region_bye_modal_is_eligible_for_double_bye_user_once_per_season(monkeypatch):
    user_team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    opponent_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    franchise_doc = _region_bye_modal_doc(user_team_id, opponent_id)
    monkeypatch.setattr(
        franchise_routes,
        "_build_user_eos_sim_scope",
        lambda franchise_doc, team_id: {"region": "A"},
    )

    assert _should_show_region_bye_modal(franchise_doc, user_team_id) is True

    franchise_doc["region_bye_modal_seen_season"] = 3
    assert _should_show_region_bye_modal(franchise_doc, user_team_id) is False

    franchise_doc["current_season"] = 4
    assert _should_show_region_bye_modal(franchise_doc, user_team_id) is True


def test_region_bye_modal_is_eligible_for_single_bye_user(monkeypatch):
    user_team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    round1_away = "bbbbbbbbbbbbbbbbbbbbbbbb"
    round1_home = "cccccccccccccccccccccccc"
    franchise_doc = _region_bye_modal_doc(user_team_id, "R1_0")
    franchise_doc["region_tournaments"]["A"]["round1"] = [
        {
            "away_team": round1_away,
            "home_team": round1_home,
            "winner": None,
            "game_id": None,
            "score": {},
        }
    ]
    monkeypatch.setattr(
        franchise_routes,
        "_build_user_eos_sim_scope",
        lambda franchise_doc, team_id: {"region": "A"},
    )

    assert _should_show_region_bye_modal(franchise_doc, user_team_id) is True


def test_region_bye_modal_excludes_other_teams_byes_eliminated_users_and_week31(monkeypatch):
    user_team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    bye_team_id = "bbbbbbbbbbbbbbbbbbbbbbbb"
    opponent_id = "cccccccccccccccccccccccc"
    franchise_doc = _region_bye_modal_doc(bye_team_id, opponent_id)
    monkeypatch.setattr(
        franchise_routes,
        "_build_user_eos_sim_scope",
        lambda franchise_doc, team_id: {"region": "A"},
    )

    assert _should_show_region_bye_modal(franchise_doc, user_team_id) is False

    franchise_doc["week"] = 31
    assert _should_show_region_bye_modal(franchise_doc, bye_team_id) is False

    franchise_doc["week"] = 30
    franchise_doc["eos_tournament_active"] = False
    assert _should_show_region_bye_modal(franchise_doc, bye_team_id) is False


def test_mark_region_bye_modal_seen_persists_current_season(monkeypatch):
    franchise_id = ObjectId()
    franchise_doc = {"_id": franchise_id, "current_season": 5}
    mock_db = MagicMock()
    monkeypatch.setattr(franchise_routes, "db", mock_db)
    monkeypatch.setattr(
        franchise_routes,
        "verify_franchise_owned_by_user",
        lambda requested_id, user_id: franchise_doc,
    )

    response = mark_region_bye_modal_seen(
        RegionByeModalSeenRequest(franchise_id=str(franchise_id)),
        user={"user_id": "test-user"},
    )

    assert response == {"seen": True, "season": 5}
    mock_db.franchises.update_one.assert_called_once_with(
        {"_id": franchise_id},
        {"$set": {"region_bye_modal_seen_season": 5}},
    )


def test_sim_rest_advances_empty_double_bye_week30_to_week31():
    franchise_id = ObjectId()
    user_team_id = ObjectId()
    opponent_id = ObjectId()
    franchise_doc = {
        "_id": franchise_id,
        "week": 30,
        "eos_tournament_active": True,
        "user_team_id": "User Team",
        "user_team_object_id": str(user_team_id),
        "results": {},
        "region_tournaments": {
            "A": {
                "round1": [],
                "final": [
                    {
                        "away_team": str(user_team_id),
                        "home_team": str(opponent_id),
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    }
                ],
                "current_round": 1,
            }
        },
    }
    franchise_routes.db.franchises.insert_one(franchise_doc)
    franchise_routes.db.teams.insert_one(
        {"_id": user_team_id, "name": "User Team", "conference": 1, "region": "A"}
    )
    try:
        response = sim_rest_of_tournament(
            SimRestOfTournamentRequest(franchise_id=str(franchise_id))
        )
        assert response == {"status": "success", "week": 31}

        saved = franchise_routes.db.franchises.find_one({"_id": franchise_id})
        assert saved["week"] == 31
        assert saved["results"]["30"] == []
        final = saved["region_tournaments"]["A"]["final"][0]
        assert final["winner"] is None
        assert final["game_id"] is None
    finally:
        franchise_routes.db.franchises.delete_one({"_id": franchise_id})
        franchise_routes.db.teams.delete_one({"_id": user_team_id})


def test_merge_phase_a_eos_preserves_cpu_r1_winners_when_stale_bracket_missing_them():
    """Regression: phase A must not $set conference_tournaments from a doc loaded before start-cpu-sims."""
    th, ta, tb, tc, td, te, tf = (str(ObjectId()) for _ in range(7))
    tw_user = str(ObjectId())
    fresh_ct = {
        "1": {
            "current_round": 1,
            "bracket": {
                "round1": [
                    {
                        "home_team": th,
                        "away_team": tw_user,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                    {
                        "home_team": ta,
                        "away_team": tb,
                        "winner": ta,
                        "game_id": "cpu-g1",
                        "score": {"home": 70, "away": 65},
                    },
                    {
                        "home_team": tc,
                        "away_team": td,
                        "winner": tc,
                        "game_id": "cpu-g2",
                        "score": {"home": 68, "away": 60},
                    },
                    {
                        "home_team": te,
                        "away_team": tf,
                        "winner": te,
                        "game_id": "cpu-g3",
                        "score": {"home": 72, "away": 71},
                    },
                ],
                "round2": [],
                "final": [],
            },
        }
    }
    stale_ct = {
        "1": {
            "current_round": 1,
            "bracket": {
                "round1": [
                    {
                        "home_team": th,
                        "away_team": tw_user,
                        "winner": tw_user,
                        "game_id": "",
                        "score": {"home": 60, "away": 70},
                    },
                    {
                        "home_team": ta,
                        "away_team": tb,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                    {
                        "home_team": tc,
                        "away_team": td,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                    {
                        "home_team": te,
                        "away_team": tf,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                ],
                "round2": [],
                "final": [],
            },
        }
    }
    merged = ft.merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(
        {"conference_tournaments": fresh_ct},
        {"conference_tournaments": stale_ct},
    )
    r1 = merged["conference_tournaments"]["1"]["bracket"]["round1"]
    assert r1[0]["winner"] == tw_user
    assert r1[0]["score"] == {"home": 60, "away": 70}
    assert r1[1]["winner"] == ta
    assert r1[1]["game_id"] == "cpu-g1"
    assert r1[2]["winner"] == tc
    assert r1[2]["game_id"] == "cpu-g2"
    assert r1[3]["winner"] == te
    assert r1[3]["game_id"] == "cpu-g3"
