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


def test_record_tournament_game_result_duplicate_cpu_skipped_when_slot_unchanged():
    """Second cpu_full with same winner/scores must not re-write (idempotent guard)."""
    away = str(ObjectId())
    home = str(ObjectId())
    franchise_doc = {
        "_id": ObjectId(),
        "conference_tournaments": {
            "1": {
                "current_round": 2,
                "bracket": {
                    "round1": [
                        {
                            "home_team": str(ObjectId()),
                            "away_team": str(ObjectId()),
                            "winner": str(ObjectId()),
                            "game_id": "g",
                            "score": {"home": 1, "away": 0},
                        }
                        for _ in range(4)
                    ],
                    "round2": [
                        {
                            "home_team": home,
                            "away_team": away,
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                        {
                            "home_team": str(ObjectId()),
                            "away_team": str(ObjectId()),
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                    ],
                    "final": [],
                },
                "seeds": {},
            }
        },
    }
    meta = {
        "away_id": away,
        "home_id": home,
        "phase": "conference",
        "conference": 1,
        "round": 2,
        "matchup_index": 0,
    }
    fid = str(ObjectId())
    ftp.record_tournament_game_result(
        franchise_doc,
        meta,
        week=28,
        franchise_id_str=fid,
        game_id="gidaaa",
        team1_id=away,
        team2_id=home,
        team1_score=65,
        team2_score=70,
        source="cpu_full",
        skip_games_upsert=True,
    )
    slot = franchise_doc["conference_tournaments"]["1"]["bracket"]["round2"][0]
    assert slot["winner"] == home
    assert slot["game_id"] == "gidaaa"
    r2 = ftp.record_tournament_game_result(
        franchise_doc,
        meta,
        week=28,
        franchise_id_str=fid,
        game_id="gidbbb",
        team1_id=away,
        team2_id=home,
        team1_score=65,
        team2_score=70,
        source="cpu_full",
        skip_games_upsert=True,
    )
    assert r2.get("duplicate_eos_record") is True
    assert slot["game_id"] == "gidaaa"


def test_record_tournament_game_result_cpu_does_not_overwrite_different_winner():
    away = str(ObjectId())
    home = str(ObjectId())
    other = str(ObjectId())
    franchise_doc = {
        "_id": ObjectId(),
        "conference_tournaments": {
            "1": {
                "current_round": 2,
                "bracket": {
                    "round1": [
                        {
                            "home_team": str(ObjectId()),
                            "away_team": str(ObjectId()),
                            "winner": str(ObjectId()),
                            "game_id": "g",
                            "score": {"home": 1, "away": 0},
                        }
                        for _ in range(4)
                    ],
                    "round2": [
                        {
                            "home_team": home,
                            "away_team": away,
                            "winner": home,
                            "game_id": "locked",
                            "score": {"home": 70, "away": 65},
                        },
                        {
                            "home_team": str(ObjectId()),
                            "away_team": str(ObjectId()),
                            "winner": None,
                            "game_id": None,
                            "score": {},
                        },
                    ],
                    "final": [],
                },
                "seeds": {},
            }
        },
    }
    meta = {
        "away_id": away,
        "home_id": home,
        "phase": "conference",
        "conference": 1,
        "round": 2,
        "matchup_index": 0,
    }
    fid = str(ObjectId())
    out = ftp.record_tournament_game_result(
        franchise_doc,
        meta,
        week=28,
        franchise_id_str=fid,
        game_id="newgid",
        team1_id=away,
        team2_id=home,
        team1_score=80,
        team2_score=60,
        source="cpu_full",
        skip_games_upsert=True,
    )
    assert out.get("skipped_non_idempotent_cpu") is True
    slot = franchise_doc["conference_tournaments"]["1"]["bracket"]["round2"][0]
    assert slot["winner"] == home
    assert slot["game_id"] == "locked"


def test_find_eos_game_meta_for_team_pair_order_insensitive():
    away = str(ObjectId())
    home = str(ObjectId())
    meta = {
        "away_id": away,
        "home_id": home,
        "phase": "conference",
        "conference": 3,
        "round": 2,
        "matchup_index": 1,
    }
    week_meta = [meta]
    assert ftp.find_eos_game_meta_for_team_pair(week_meta, away, home) == meta
    assert ftp.find_eos_game_meta_for_team_pair(week_meta, home, away) == meta
    assert ftp.find_eos_game_meta_for_team_pair(week_meta, away, str(ObjectId())) is None
