from BackEnd.api import franchise_routes
from BackEnd.api.franchise_routes import _get_user_eos_phase_status, _should_use_tbt_for_eos_game


def test_conference_weeks_only_user_conference_uses_tbt():
    user_scope = {
        "active": True,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(27, {"phase": "conference", "conference": 3}, user_scope) is True
    assert _should_use_tbt_for_eos_game(28, {"phase": "conference", "conference": 4}, user_scope) is False


def test_week_29_uses_user_region_pair_for_tbt():
    user_scope = {
        "active": True,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(29, {"phase": "conference", "conference": 3}, user_scope) is True
    assert _should_use_tbt_for_eos_game(29, {"phase": "conference", "conference": 4}, user_scope) is True
    assert _should_use_tbt_for_eos_game(29, {"phase": "conference", "conference": 5}, user_scope) is False


def test_region_weeks_only_user_region_uses_tbt():
    user_scope = {
        "active": True,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(30, {"phase": "region", "region": "B"}, user_scope) is True
    assert _should_use_tbt_for_eos_game(31, {"phase": "region", "region": "C"}, user_scope) is False


def test_national_weeks_use_tbt_when_user_is_active():
    user_scope = {
        "active": True,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(32, {"phase": "national"}, user_scope) is True
    assert _should_use_tbt_for_eos_game(34, {"phase": "national"}, user_scope) is True


def test_all_eos_games_use_csg_when_user_is_not_active():
    user_scope = {
        "active": False,
        "conference": 3,
        "region": "B",
        "region_conferences": (3, 4),
    }

    assert _should_use_tbt_for_eos_game(28, {"phase": "conference", "conference": 3}, user_scope) is False
    assert _should_use_tbt_for_eos_game(30, {"phase": "region", "region": "B"}, user_scope) is False
    assert _should_use_tbt_for_eos_game(33, {"phase": "national"}, user_scope) is False


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
    assert week_29_status["eliminated_from_current_phase"] is True

    week_30_status = _get_user_eos_phase_status(franchise_doc, user_team_id, 30)
    assert week_30_status["active_this_week"] is True
    assert week_30_status["has_bye_this_week"] is True
    assert week_30_status["eliminated_from_current_phase"] is False
