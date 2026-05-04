"""Unit tests for centralized EOS tournament recording."""

import pytest
from bson import ObjectId

from BackEnd.tournament import franchise_tournament_progression as ftp


def test_record_tournament_game_result_rejects_team_mismatch():
    away = str(ObjectId())
    home = str(ObjectId())
    other = str(ObjectId())
    franchise_doc: dict = {"_id": ObjectId()}
    meta = {
        "away_id": away,
        "home_id": home,
        "phase": "conference",
        "conference": 1,
        "round": 1,
        "matchup_index": 0,
    }
    with pytest.raises(ValueError, match="do not match EOS meta"):
        ftp.record_tournament_game_result(
            franchise_doc,
            meta,
            week=27,
            franchise_id_str=str(ObjectId()),
            game_id="g1",
            team1_id=away,
            team2_id=other,
            team1_score=50,
            team2_score=60,
            source="user",
        )


def test_find_user_eos_game_meta_empty_calendar_uses_playable():
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
                            "game_id": f"g{i}",
                            "score": {},
                        }
                        for i in range(4)
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
    g = ftp.find_user_eos_game_meta(
        franchise_doc,
        week_games_meta=[],
        user_team_id_str=uid_user,
        week=29,
    )
    assert g is not None
    assert g["phase"] == "conference"
    assert g["round"] == 2
    assert g["matchup_index"] == 1
