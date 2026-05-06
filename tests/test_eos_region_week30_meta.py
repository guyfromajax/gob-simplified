"""Region EOS week 30: get_eos_week_games must list finals when round1 is empty (double-bye)."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bson import ObjectId

from BackEnd.tournament import franchise_tournament as ft


def _tid():
    return str(ObjectId())


def test_week30_double_bye_region_exposes_final_not_empty_meta():
    t1, t2 = _tid(), _tid()
    franchise_doc = {
        "region_tournaments": {
            "A": {
                "round1": [],
                "final": [
                    {
                        "away_team": t1,
                        "home_team": t2,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    }
                ],
                "current_round": 1,
            },
        }
    }
    games = ft.get_eos_week_games(franchise_doc, 30, include_completed=False)
    assert len(games) == 1
    g = games[0]
    assert g["phase"] == "region"
    assert g["region"] == "A"
    assert g["round"] == 2
    assert g["matchup_index"] == 0
    assert str(g["away_id"]) == t1
    assert str(g["home_id"]) == t2


def test_week30_four_team_region_only_round1_no_duplicate_final():
    a1, a2, a3, a4 = _tid(), _tid(), _tid(), _tid()
    franchise_doc = {
        "region_tournaments": {
            "B": {
                "round1": [
                    {"away_team": a1, "home_team": a2, "winner": None, "game_id": None, "score": {}},
                    {"away_team": a3, "home_team": a4, "winner": None, "game_id": None, "score": {}},
                ],
                "final": [{"away_team": "R1_0", "home_team": "R1_1", "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            },
        }
    }
    games = ft.get_eos_week_games(franchise_doc, 30, include_completed=False)
    assert len(games) == 2
    assert all(x["round"] == 1 for x in games)


def test_week30_three_team_one_r1_only():
    b1, b2, b3 = _tid(), _tid(), _tid()
    franchise_doc = {
        "region_tournaments": {
            "C": {
                "round1": [
                    {"away_team": b2, "home_team": b3, "winner": None, "game_id": None, "score": {}},
                ],
                "final": [{"away_team": "R1_0", "home_team": b1, "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            },
        }
    }
    games = ft.get_eos_week_games(franchise_doc, 30, include_completed=False)
    assert len(games) == 1
    assert games[0]["round"] == 1


def test_week30_all_eight_regions_mixed_double_bye_and_full():
    """Sim-rest needs non-empty meta when every region is represented; mix 2-team and 4-team."""
    ids = [str(ObjectId()) for _ in range(24)]
    regions = {}
    for idx, letter in enumerate(ft.REGION_LETTERS):
        if idx < 4:
            # double-bye: final only
            t1, t2 = ids[idx * 2], ids[idx * 2 + 1]
            regions[letter] = {
                "round1": [],
                "final": [{"away_team": t1, "home_team": t2, "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            }
        else:
            base = 8 + (idx - 4) * 4
            regions[letter] = {
                "round1": [
                    {"away_team": ids[base], "home_team": ids[base + 1], "winner": None, "game_id": None, "score": {}},
                    {"away_team": ids[base + 2], "home_team": ids[base + 3], "winner": None, "game_id": None, "score": {}},
                ],
                "final": [{"away_team": "R1_0", "home_team": "R1_1", "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            }
    franchise_doc = {"region_tournaments": regions}
    games = ft.get_eos_week_games(franchise_doc, 30, include_completed=False)
    # 4 regions × 1 final + 4 regions × 2 R1 = 12
    assert len(games) == 12
    finals_week30 = [g for g in games if g.get("round") == 2]
    r1_week30 = [g for g in games if g.get("round") == 1]
    assert len(finals_week30) == 4
    assert len(r1_week30) == 8


def test_week30_round1_nonempty_but_no_playable_r1_still_surfaces_final():
    """Legacy / odd shapes: round1 rows exist but none are real R1 games; final is ready."""
    t1, t2 = _tid(), _tid()
    franchise_doc = {
        "region_tournaments": {
            "E": {
                "round1": [
                    {
                        "away_team": "R1_0",
                        "home_team": "R1_1",
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                ],
                "final": [
                    {
                        "away_team": t1,
                        "home_team": t2,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    }
                ],
                "current_round": 1,
            },
        }
    }
    games = ft.get_eos_week_games(franchise_doc, 30, include_completed=False)
    assert len(games) == 1
    assert games[0]["round"] == 2
    assert str(games[0]["away_id"]) == t1
    assert str(games[0]["home_id"]) == t2


def test_week30_include_completed_skips_won_final():
    t1, t2 = _tid(), _tid()
    franchise_doc = {
        "region_tournaments": {
            "D": {
                "round1": [],
                "final": [
                    {
                        "away_team": t1,
                        "home_team": t2,
                        "winner": t1,
                        "game_id": "g1",
                        "score": {"home": 60, "away": 55},
                    }
                ],
                "current_round": 1,
            },
        }
    }
    games = ft.get_eos_week_games(franchise_doc, 30, include_completed=False)
    assert games == []
    hist = ft.get_eos_week_games(franchise_doc, 30, include_completed=True)
    assert len(hist) == 1
    assert hist[0].get("winner") == t1


def test_user_has_region_r1_bye_waiting_three_team_bracket():
    """Champ in final vs R1_0 placeholder while other conf plays R1 — no playable row for bye team."""
    b1, b2, b3 = _tid(), _tid(), _tid()
    franchise_doc = {
        "week": 30,
        "eos_tournament_active": True,
        "region_tournaments": {
            "C": {
                "round1": [
                    {"away_team": b2, "home_team": b3, "winner": None, "game_id": None, "score": {}},
                ],
                "final": [{"away_team": "R1_0", "home_team": b1, "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            },
        },
    }
    assert ft.user_has_region_round1_bye_waiting(franchise_doc, b1, "C") is True
    assert ft.user_has_region_round1_bye_waiting(franchise_doc, b2, "C") is False
    assert ft.user_has_region_round1_bye_waiting(franchise_doc, b3, "C") is False


def test_user_has_region_r1_bye_waiting_false_week31():
    b1, b2, b3 = _tid(), _tid(), _tid()
    franchise_doc = {
        "week": 31,
        "eos_tournament_active": True,
        "region_tournaments": {
            "C": {
                "round1": [
                    {"away_team": b2, "home_team": b3, "winner": None, "game_id": None, "score": {}},
                ],
                "final": [{"away_team": "R1_0", "home_team": b1, "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            },
        },
    }
    assert ft.user_has_region_round1_bye_waiting(franchise_doc, b1, "C") is False
