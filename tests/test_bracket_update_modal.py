"""Bracket update modal payload after EOS round completion."""
from copy import deepcopy

from BackEnd.api import franchise_routes as fr


def _conf_bracket_with_r1_winner():
    return {
        "round1": [
            {
                "home_team": "t1",
                "away_team": "t2",
                "winner": "t1",
                "score": {"t1": 70, "t2": 65},
            },
            {"home_team": "t3", "away_team": "t4"},
            {"home_team": "t5", "away_team": "t6"},
            {"home_team": "t7", "away_team": "t8"},
        ],
        "round2": [],
        "final": [],
    }


def test_bracket_update_modal_week_28_conference():
    franchise_doc = {
        "current_season": 2,
        "week": 28,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "3": {
                "bracket": _conf_bracket_with_r1_winner(),
                "seeds": {"t1": 1},
            }
        },
        fr.BRACKET_UPDATE_SEEN_FIELD: {},
    }
    team_doc = {"conference": 3, "region": "B"}

    payload = fr._build_bracket_update_modal_payload(franchise_doc, team_doc, 28)
    assert payload is not None
    assert payload["eligible"] is True
    assert payload["tier"] == "conference"
    assert payload["layout"] == "full"
    assert payload["update_key"] == "update:conference:2:28"
    assert payload["bracket"]["round1"][0]["winner"] == "t1"


def test_bracket_update_modal_skips_when_already_seen():
    franchise_doc = {
        "current_season": 1,
        "week": 29,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "1": {"bracket": _conf_bracket_with_r1_winner(), "seeds": {}},
        },
        fr.BRACKET_UPDATE_SEEN_FIELD: {"update:conference:1:29": True},
    }
    team_doc = {"conference": 1, "region": "A"}
    assert fr._build_bracket_update_modal_payload(franchise_doc, team_doc, 29) is None


def test_bracket_update_modal_skips_phase_start_reveal_weeks():
    franchise_doc = {
        "current_season": 1,
        "week": 27,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "1": {"bracket": _conf_bracket_with_r1_winner(), "seeds": {}},
        },
    }
    team_doc = {"conference": 1, "region": "A"}
    assert fr._build_bracket_update_modal_payload(franchise_doc, team_doc, 27) is None


def test_bracket_reveal_still_sanitizes_unplayed_round():
    raw = deepcopy(_conf_bracket_with_r1_winner())
    franchise_doc = {
        "current_season": 1,
        "week": 27,
        "eos_tournament_active": True,
        "conference_tournaments": {"1": {"bracket": raw, "seeds": {}}},
        fr.BRACKET_REVEAL_SEEN_FIELD: {},
    }
    team_doc = {"conference": 1, "region": "A"}
    # Force round1 not started for reveal eligibility
    for m in franchise_doc["conference_tournaments"]["1"]["bracket"]["round1"]:
        m.pop("winner", None)
        m["score"] = {}

    payload = fr._build_bracket_reveal_modal_payload(franchise_doc, team_doc, 27)
    assert payload is not None
    assert payload["bracket"]["round1"][0].get("winner") is None


def _dual_bye_region_doc():
    return {
        "current_season": 4,
        "eos_tournament_active": True,
        "region_tournaments": {
            "B": {
                "round1": [],
                "final": [
                    {
                        "away_team": "active-user",
                        "home_team": "other-bye-team",
                        "winner": None,
                        "score": {},
                    }
                ],
                "current_round": 1,
                "seeds": {},
            }
        },
    }


def test_region_reveal_week_30_accepts_active_user_dual_bye_final():
    payload = fr._build_bracket_reveal_modal_payload(
        _dual_bye_region_doc(),
        {"team_id": "active-user", "conference": 3, "region": "B"},
        30,
    )
    assert payload is not None
    assert payload["tier"] == "region"
    assert payload["bracket"]["round1"] == []
    assert payload["bracket"]["final"][0]["away_team"] == "active-user"


def test_region_update_week_31_accepts_eliminated_user_region_dual_bye_final():
    payload = fr._build_bracket_update_modal_payload(
        _dual_bye_region_doc(),
        {"team_id": "eliminated-user", "conference": 3, "region": "B"},
        31,
    )
    assert payload is not None
    assert payload["tier"] == "region"
    assert payload["bracket"]["round1"] == []
    assert payload["bracket"]["final"][0]["home_team"] == "other-bye-team"


def test_region_direct_final_requires_two_concrete_teams():
    doc = _dual_bye_region_doc()
    doc["region_tournaments"]["B"]["final"][0]["home_team"] = "R1_0"
    assert fr._build_bracket_reveal_modal_payload(doc, {"region": "B"}, 30) is None
    assert fr._build_bracket_update_modal_payload(doc, {"region": "B"}, 31) is None


def test_bracket_update_modal_week_35_national_after_eos():
    franchise_doc = {
        "current_season": 1,
        "week": 35,
        "eos_tournament_active": False,
        "national_tournament": {
            "bracket": {
                "round1": [{"home_team": "a", "away_team": "b", "winner": "a", "score": {}}],
                "round2": [{"home_team": "a", "away_team": "c", "winner": "a", "score": {}}],
                "final": [{"home_team": "a", "away_team": "d", "winner": "a", "score": {}}],
            },
            "seeds": {},
        },
        fr.BRACKET_UPDATE_SEEN_FIELD: {},
    }
    team_doc = {"conference": 1, "region": "A"}
    payload = fr._build_bracket_update_modal_payload(franchise_doc, team_doc, 35)
    assert payload is not None
    assert payload["tier"] == "national"
