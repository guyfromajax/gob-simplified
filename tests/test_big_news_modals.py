"""Big News modal eligibility helpers (bracket reveal + recruiting results)."""

from copy import deepcopy

from BackEnd.api import franchise_routes as fr


def _conf_bracket():
    return {
        "round1": [
            {"home_team": "a", "away_team": "b"},
            {"home_team": "c", "away_team": "d"},
            {"home_team": "e", "away_team": "f"},
            {"home_team": "g", "away_team": "h"},
        ],
        "round2": [],
        "final": [],
    }


def test_bracket_reveal_eligible_conference_week_27():
    franchise_doc = {
        "current_season": 3,
        "eos_tournament_active": True,
        "conference_tournaments": {
            "1": {"bracket": _conf_bracket(), "seeds": {"a": 1}},
        },
        fr.BRACKET_REVEAL_SEEN_FIELD: {},
    }
    team_doc = {"conference": 1, "region": "A"}
    payload = fr._build_bracket_reveal_modal_payload(franchise_doc, team_doc, 27)
    assert payload is not None
    assert payload["tier"] == "conference"
    assert payload["reveal_key"] == "conference:3"
    assert payload["bracket"]["round2"] == []


def test_bracket_reveal_skips_when_round1_started():
    bracket = _conf_bracket()
    bracket["round1"][0]["winner"] = "a"
    franchise_doc = {
        "current_season": 3,
        "eos_tournament_active": True,
        "conference_tournaments": {"1": {"bracket": bracket, "seeds": {}}},
        fr.BRACKET_REVEAL_SEEN_FIELD: {},
    }
    team_doc = {"conference": 1}
    assert fr._build_bracket_reveal_modal_payload(franchise_doc, team_doc, 27) is None


def test_bracket_reveal_skips_when_already_seen():
    franchise_doc = {
        "current_season": 3,
        "eos_tournament_active": True,
        "conference_tournaments": {"1": {"bracket": _conf_bracket(), "seeds": {}}},
        fr.BRACKET_REVEAL_SEEN_FIELD: {"conference:3": True},
    }
    team_doc = {"conference": 1}
    assert fr._build_bracket_reveal_modal_payload(franchise_doc, team_doc, 27) is None


def test_recruiting_results_modal_eligible():
    franchise_doc = {
        "current_season": 2,
        "week_35_recruiting_ran": True,
        fr.RECRUITING_RESULTS_MODAL_SEEN_SEASON_FIELD: 0,
        fr.WEEK_35_RECRUITING_RESULTS_FIELD: {
            "signed_players": [
                {
                    "team_id": "team1",
                    "name": "Alex Smith",
                    "pos": "SF",
                    "archetype": "Slasher",
                    "height": 79,
                    "weight": 210,
                    "rt": 44,
                }
            ]
        },
    }
    payload = fr._build_recruiting_results_modal_payload(franchise_doc, "team1")
    assert payload is not None
    assert payload["count"] == 1
    assert payload["recruits"][0]["name"] == "Alex Smith"


def test_recruiting_results_modal_skips_when_seen():
    franchise_doc = {
        "current_season": 2,
        "week_35_recruiting_ran": True,
        fr.RECRUITING_RESULTS_MODAL_SEEN_SEASON_FIELD: 2,
        fr.WEEK_35_RECRUITING_RESULTS_FIELD: {"signed_players": [{"team_id": "team1", "name": "X"}]},
    }
    assert fr._build_recruiting_results_modal_payload(franchise_doc, "team1") is None
