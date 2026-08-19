import json
import subprocess
from pathlib import Path

import pytest

from BackEnd.utils.community_highlights import (
    _eos_tournament_round_label,
    _overtime_count_from_game_doc,
    _overtime_phrase,
    build_community_highlight_pending,
)


ROOT = Path(__file__).resolve().parents[1]
MODE_SELECT_JS = ROOT / "FrontEnd/static/mode-select.js"


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


def _render_standard_copy(entry: dict) -> str:
    source = MODE_SELECT_JS.read_text(encoding="utf-8")
    start = source.index("function chStandardCopyHtml")
    end = source.index("// FTE v2 debut entry", start)
    script = "\n".join([
        "function escapeHtmlMs(v) { return String(v); }",
        "function chUsernameHtml(entry) { return entry.username; }",
        source[start:end],
        f"process.stdout.write(chStandardCopyHtml({json.dumps(entry)}));",
    ])
    return subprocess.check_output(["node", "-e", script], cwd=ROOT, text=True)


def test_standard_overtime_and_tournament_copy_are_exact():
    base = {
        "username": "California",
        "user_team_name": "Lancaster",
        "opponent_name": "Xavien",
        "user_score": 60,
        "opponent_score": 70,
        "rank_label": "#25",
        "user_team_record": "20-6",
        "overtime_count": 0,
    }
    tournament_loss = dict(base, user_won=False, tournament_round_label="Conference Tourney Championship")
    assert _render_standard_copy(tournament_loss) == (
        "California, coaching #25 Lancaster, lost to Xavien 60-70 "
        "in the Conference Tourney Championship."
    )

    regular_ot = dict(base, user_won=True, user_score=95, opponent_score=92, overtime_count=1)
    assert _render_standard_copy(regular_ot) == (
        "California, coaching Lancaster, beat Xavien 95-92 in OT. "
        "Lancaster is now 20-6 & ranked #25 in the nation."
    )

    for count, phrase in ((2, "double OT"), (3, "triple OT"), (4, "4 overtime quarters")):
        overtime_entry = dict(base, user_won=True, user_score=95, opponent_score=92, overtime_count=count)
        assert _render_standard_copy(overtime_entry) == (
            f"California, coaching Lancaster, beat Xavien 95-92 in {phrase}. "
            "Lancaster is now 20-6 & ranked #25 in the nation."
        )

    tournament_double_ot = dict(
        base,
        user_won=True,
        user_score=81,
        opponent_score=79,
        overtime_count=2,
        tournament_round_label="National Tourney Semifinals",
    )
    assert _render_standard_copy(tournament_double_ot) == (
        "California, coaching #25 Lancaster, beat Xavien 81-79 in double OT "
        "in the National Tourney Semifinals."
    )
