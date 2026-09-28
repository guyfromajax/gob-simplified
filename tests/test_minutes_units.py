"""Game MIN is seconds. Display and the limited-minutes trigger use whole minutes."""

from BackEnd.data.tutorial_rosters import (
    COMPUTER_TEAM_STAT_TEMPLATE,
    USER_TEAM_STAT_TEMPLATE,
)
from BackEnd.pgpc_qualification import get_qualifying_pgpc_questions
from BackEnd.pgpc_template_substitution import build_pgpc_substitutions
from BackEnd.utils.minutes_display import display_minutes
from BackEnd.utils.stat_updater import display_minutes as updater_display_minutes

# Design minutes from the tutorial tables. Stored MIN is those values in seconds.
_USER_MINUTES = {
    "starting_pg": 21, "starting_sg": 24, "starting_sf": 20, "starting_pf": 21,
    "starting_c": 19, "backup_1": 12, "backup_2": 11, "backup_3": 8,
    "backup_4": 4, "backup_5": 0, "backup_6": 0, "backup_7": 0,
}
_CPU_MINUTES = {
    "starting_pg": 21, "starting_sg": 23, "starting_sf": 23, "starting_pf": 18,
    "starting_c": 16, "backup_1": 12, "backup_2": 11, "backup_3": 8,
    "backup_4": 5, "backup_5": 3, "backup_6": 0, "backup_7": 0,
}


def test_display_minutes_matches_the_box_score_floor():
    assert display_minutes is updater_display_minutes
    assert display_minutes(720) == 12
    assert display_minutes(0) == 0
    assert display_minutes(59) == 0
    assert display_minutes(19 * 60 + 59) == 19
    assert display_minutes(None) == 0


def test_player_min_substitution_is_whole_minutes():
    game = {"teams": {}, "players": []}
    row = {"playerId": "p1", "stats": {"MIN": 720, "PTS": 4, "F": 1}}
    subs = build_pgpc_substitutions(game, {"user_team_id": "u", "opponent_team_id": "o"}, slot_player=row)
    assert subs["{player_min}"] == "12"


def _limited_game(seconds):
    return {
        "players": [{
            "playerId": "p1",
            "team_id": "T_USER",
            "stats": {"MIN": seconds, "PTS": 2},
        }],
        "teams": {
            "T_USER": {"team_id": "T_USER", "score": 60},
            "T_OPP": {"team_id": "T_OPP", "score": 70},
        },
    }


def _limited_ctx():
    return {
        "user_team_id": "T_USER",
        "opponent_team_id": "T_OPP",
        "player_overall_rt": {"p1": 80},
        "user_won": False,
    }


def test_limited_minutes_trigger_uses_whole_minutes():
    fired = {q["id"] for q in get_qualifying_pgpc_questions(_limited_game(19 * 60), _limited_ctx())}
    quiet = {q["id"] for q in get_qualifying_pgpc_questions(_limited_game(21 * 60), _limited_ctx())}
    assert "benched_star_01" in fired
    assert "benched_star_01" not in quiet


def test_tutorial_min_is_stored_in_seconds():
    for slot, minutes in _USER_MINUTES.items():
        stored = USER_TEAM_STAT_TEMPLATE[slot]["MIN"]
        assert stored == minutes * 60
        assert display_minutes(stored) == minutes
    for slot, minutes in _CPU_MINUTES.items():
        stored = COMPUTER_TEAM_STAT_TEMPLATE[slot]["MIN"]
        assert stored == minutes * 60
        assert display_minutes(stored) == minutes
    assert sum(display_minutes(row["MIN"]) for row in USER_TEAM_STAT_TEMPLATE.values()) == 140
    assert sum(display_minutes(row["MIN"]) for row in COMPUTER_TEAM_STAT_TEMPLATE.values()) == 140
