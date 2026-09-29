"""Highlight copy rules.

The client-side sentence builder these tests also covered (chStandardCopyHtml
in mode-select.js) went with Community Highlights when Ch7 took the feed off
Home Base. The phrasing rules it drew on are server-side and still checked
here; the championship announcements the server assembles itself are covered
below.
"""

import pytest

from BackEnd.utils.community_highlights import (
    _eos_tournament_round_label,
    _overtime_count_from_game_doc,
    _overtime_phrase,
    build_community_highlight_pending,
)


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({"phase": "conference", "round": 1}, "Conference Tourney First Round"),
        ({"phase": "conference", "round": 2}, "Conference Tourney Semifinals"),
        ({"phase": "conference", "round": 3}, "Conference Tourney Championship"),
        ({"phase": "region", "round": 1}, "Region Tourney Semifinals"),
        ({"phase": "region", "round": 2}, "Region Tourney Championship"),
        ({"phase": "national", "round": 1}, "National Tourney First Round"),
        ({"phase": "national", "round": 2}, "National Tourney Semifinals"),
        ({"phase": "national", "round": 3}, "National Tourney Championship"),
    ],
)
def test_eos_tournament_round_labels(meta, expected):
    assert _eos_tournament_round_label(meta) == expected


def test_pending_keeps_championship_win_behavior_and_labels_all_tournament_games():
    loss = build_community_highlight_pending(
        week=29,
        user_team_id_str="user",
        user_row={"away_id": "user", "home_id": "opp", "away_score": 60, "home_score": 70},
        gp_delta=-1,
        eos_game_meta={"phase": "conference", "round": 3, "conference": 12},
    )
    assert loss["tournament_round_label"] == "Conference Tourney Championship"
    assert "eos_championship" not in loss

    win = build_community_highlight_pending(
        week=29,
        user_team_id_str="user",
        user_row={"away_id": "user", "home_id": "opp", "away_score": 71, "home_score": 70},
        gp_delta=5,
        eos_game_meta={"phase": "conference", "round": 3, "conference": 12},
    )
    assert win["eos_championship"]["kind"] == "conf_tournament"


@pytest.mark.parametrize(
    ("period_count", "expected_count", "expected_phrase"),
    [(4, 0, ""), (5, 1, "in OT"), (6, 2, "in double OT"),
     (7, 3, "in triple OT"), (8, 4, "in 4 overtime quarters")],
)
def test_overtime_count_and_phrase_from_played_periods(period_count, expected_count, expected_phrase):
    doc = {"teams": {"user": {"points_by_quarter": [10] * period_count}}}
    count = _overtime_count_from_game_doc(doc)
    assert count == expected_count
    assert _overtime_phrase(count) == expected_phrase
