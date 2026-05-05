"""Region bracket reconcile + RS#1 inference for EOS materialization."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from bson import ObjectId

from BackEnd.tournament import franchise_tournament as ft


def _tid():
    return str(ObjectId())


def test_infer_rs1_from_bracket_when_seeds_missing():
    t1, t8 = _tid(), _tid()
    ct = {
        "champion": t1,
        "seeds": {},
        "bracket": {
            "round1": [
                {
                    "home_team": t1,
                    "away_team": t8,
                    "winner": None,
                    "game_id": None,
                    "score": {},
                },
            ],
            "round2": [],
            "final": [],
        },
    }
    assert ft._infer_rs1_team_id_from_conference_tournament(ct) == t1


def test_get_conf_rs1_falls_back_when_seeds_empty():
    c1, c2, c3, c4 = _tid(), _tid(), _tid(), _tid()
    franchise_doc = {
        "conference_tournaments": {
            "1": {
                "champion": c1,
                "seeds": {},
                "bracket": {
                    "round1": [
                        {
                            "home_team": c1,
                            "away_team": c2,
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                    ],
                    "round2": [],
                    "final": [],
                },
            },
            "2": {
                "champion": c3,
                "seeds": {},
                "bracket": {
                    "round1": [
                        {
                            "home_team": c3,
                            "away_team": c4,
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                    ],
                    "round2": [],
                    "final": [],
                },
            },
        }
    }
    ch, rs1 = ft._get_conf_champions_and_rs1(franchise_doc, [], {})
    assert ch[1] == c1
    assert rs1[1] == c1
    assert ch[2] == c3
    assert rs1[2] == c3


def test_reconcile_replaces_fully_unplayed_incomplete_region():
    """Corrupt region A (half-filled R1); canonical is 4-team (two R1 games). All unplayed → wholesale replace."""
    teams = [_tid() for _ in range(16)]
    c1 = teams[0:8]
    c2 = teams[8:16]
    franchise_doc = {
        "conference_tournaments": {
            # Champion ≠ #1 seed so region is 4-team (no double-bye).
            "1": {"champion": c1[7], "seeds": {c1[i]: i + 1 for i in range(8)}},
            "2": {"champion": c2[7], "seeds": {c2[i]: i + 1 for i in range(8)}},
        },
        "region_tournaments": {
            "A": {
                "round1": [
                    {
                        "away_team": c1[0],
                        "home_team": None,
                        "winner": None,
                        "game_id": None,
                        "score": {},
                    },
                ],
                "final": [{"away_team": "R1_0", "home_team": "R1_1", "winner": None, "game_id": None, "score": {}}],
                "current_round": 1,
            },
        },
    }
    team_docs = [{"_id": ObjectId(t), "conference": 1, "region": "A"} for t in c1] + [
        {"_id": ObjectId(t), "conference": 2, "region": "A"} for t in c2
    ]
    mock_teams = MagicMock()
    mock_teams.find.return_value = team_docs

    out = ft.reconcile_region_tournaments_with_canonical(franchise_doc, mock_teams, teams)
    assert out is not None
    r1 = out["A"]["round1"]
    assert len(r1) == 2
    for m in r1:
        assert m.get("away_team")
        assert m.get("home_team")
