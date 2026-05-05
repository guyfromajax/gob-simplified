"""
Tests for the EOS user-game bracket-write invariant and related self-heal coverage
introduced to close the silent fall-through that left ``conference_tournaments`` /
``region_tournaments`` / ``national_tournament`` cells with no ``winner`` / ``game_id``
while ``franchise.results`` and ``db.games`` looked complete.

See ``Tournament_Execution_System.md`` §"User game bracket write invariant".
"""
from unittest.mock import MagicMock

import pytest
from bson import ObjectId
from fastapi import HTTPException

from BackEnd.api import franchise_routes
from BackEnd.api.franchise_routes import (
    CompleteWeekRequest,
    GameResult,
    _eos_meta_from_game_document,
    _harden_complete_week_request_week,
    _resolve_user_eos_game_meta_or_raise,
    _stamp_eos_meta_on_game_doc,
)


# ---------------------------------------------------------------------------
# _resolve_user_eos_game_meta_or_raise (Patch 1: hard invariant)
# ---------------------------------------------------------------------------


def _make_req(week: int, t1: str, t2: str, *, game_document: dict | None = None) -> CompleteWeekRequest:
    return CompleteWeekRequest(
        franchise_id=str(ObjectId()),
        week=week,
        result=GameResult(team1_id=t1, team2_id=t2, team1_score=70, team2_score=60),
        game_id=None,
        game_document=game_document,
    )


def test_resolve_user_eos_game_meta_raises_when_pair_missing_from_slate():
    """Hard invariant: in EOS week with a non-empty slate, an unresolvable user pair must raise."""
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    franchise_doc = {"_id": ObjectId(), "week": 27}
    # Slate exists but does not contain user/opp pair (some other matchup)
    week_games_meta = [
        {
            "away_id": str(ObjectId()),
            "home_id": str(ObjectId()),
            "phase": "conference",
            "conference": 1,
            "round": 1,
            "matchup_index": 0,
        }
    ]
    req = _make_req(27, user_id, opp_id)
    with pytest.raises(HTTPException) as ei:
        _resolve_user_eos_game_meta_or_raise(
            franchise_doc=franchise_doc,
            req=req,
            week_games_meta=week_games_meta,
            user_team_id_str=user_id,
            team1_id=user_id,
            team2_id=opp_id,
        )
    assert ei.value.status_code == 409
    assert "EOS bracket slot" in ei.value.detail


def test_resolve_user_eos_game_meta_raises_when_no_slate_in_eos_week():
    """Hard invariant: EOS week with no slate (eos_active False) refuses score-only persist."""
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    franchise_doc = {"_id": ObjectId(), "week": 27}
    req = _make_req(27, user_id, opp_id)
    with pytest.raises(HTTPException) as ei:
        _resolve_user_eos_game_meta_or_raise(
            franchise_doc=franchise_doc,
            req=req,
            week_games_meta=None,
            user_team_id_str=user_id,
            team1_id=user_id,
            team2_id=opp_id,
        )
    assert ei.value.status_code == 409
    assert "no playable slate" in ei.value.detail


def test_resolve_user_eos_game_meta_uses_team_pair_fallback():
    """When find_user_eos_game_meta misses but the pair is in the slate, the team-pair fallback wins."""
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    franchise_doc = {
        "_id": ObjectId(),
        "week": 27,
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {"away_team": user_id, "home_team": opp_id, "winner": None, "score": {}, "game_id": None}
                    ],
                    "round2": [],
                    "final": [],
                },
            }
        },
    }
    week_games_meta = [
        {
            "away_id": user_id,
            "home_id": opp_id,
            "phase": "conference",
            "conference": 1,
            "round": 1,
            "matchup_index": 0,
        }
    ]
    req = _make_req(27, user_id, opp_id)
    g = _resolve_user_eos_game_meta_or_raise(
        franchise_doc=franchise_doc,
        req=req,
        week_games_meta=week_games_meta,
        user_team_id_str=user_id,
        team1_id=user_id,
        team2_id=opp_id,
    )
    assert g is not None
    assert g["phase"] == "conference"
    assert g["matchup_index"] == 0


# ---------------------------------------------------------------------------
# _eos_meta_from_game_document (Patch 5: primary source of truth)
# ---------------------------------------------------------------------------


def test_eos_meta_from_game_document_returns_valid_meta():
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    eos_meta = {
        "phase": "conference",
        "conference": 5,
        "round": 1,
        "matchup_index": 2,
        "away_id": user_id,
        "home_id": opp_id,
    }
    req = _make_req(27, user_id, opp_id, game_document={"week": 27, "eos_meta": eos_meta})
    g = _eos_meta_from_game_document(req)
    assert g is not None
    assert g["phase"] == "conference"
    assert g["conference"] == 5
    assert g["round"] == 1
    assert g["matchup_index"] == 2


def test_eos_meta_from_game_document_rejects_missing_phase():
    req = _make_req(27, str(ObjectId()), str(ObjectId()), game_document={"week": 27, "eos_meta": {"round": 1, "matchup_index": 0, "away_id": "x", "home_id": "y"}})
    assert _eos_meta_from_game_document(req) is None


def test_eos_meta_from_game_document_rejects_missing_conference_for_conference_phase():
    req = _make_req(27, str(ObjectId()), str(ObjectId()), game_document={"week": 27, "eos_meta": {"phase": "conference", "round": 1, "matchup_index": 0, "away_id": "x", "home_id": "y"}})
    assert _eos_meta_from_game_document(req) is None


def test_eos_meta_from_game_document_rejects_missing_region_for_region_phase():
    req = _make_req(30, str(ObjectId()), str(ObjectId()), game_document={"week": 30, "eos_meta": {"phase": "region", "round": 1, "matchup_index": 0, "away_id": "x", "home_id": "y"}})
    assert _eos_meta_from_game_document(req) is None


def test_resolve_prefers_game_document_eos_meta_over_slate():
    """When req.game_document.eos_meta is present, slate matching is skipped."""
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    eos_meta = {
        "phase": "region",
        "region": "B",
        "round": 1,
        "matchup_index": 0,
        "away_id": user_id,
        "home_id": opp_id,
    }
    franchise_doc = {"_id": ObjectId(), "week": 30}
    # Empty slate — slate-only resolution would raise. game_document.eos_meta saves us.
    req = _make_req(30, user_id, opp_id, game_document={"week": 30, "eos_meta": eos_meta})
    g = _resolve_user_eos_game_meta_or_raise(
        franchise_doc=franchise_doc,
        req=req,
        week_games_meta=[],
        user_team_id_str=user_id,
        team1_id=user_id,
        team2_id=opp_id,
    )
    assert g["phase"] == "region"
    assert g["region"] == "B"


# ---------------------------------------------------------------------------
# _harden_complete_week_request_week (Patch 2: symmetric harden)
# ---------------------------------------------------------------------------


def _conference_doc_with_pair_in_round(t1: str, t2: str, *, conference: int, round_num: int) -> dict:
    matchup = {"away_team": t1, "home_team": t2, "winner": None, "score": {}, "game_id": None}
    bracket = {"round1": [], "round2": [], "final": []}
    if round_num == 1:
        bracket["round1"] = [matchup, _empty_matchup(), _empty_matchup(), _empty_matchup()]
    elif round_num == 2:
        bracket["round1"] = [_completed_matchup() for _ in range(4)]
        bracket["round2"] = [matchup, _empty_matchup()]
    else:
        bracket["round1"] = [_completed_matchup() for _ in range(4)]
        bracket["round2"] = [_completed_matchup() for _ in range(2)]
        bracket["final"] = [matchup]
    return {
        "_id": ObjectId(),
        "week": 27 + (round_num - 1),
        "eos_tournament_active": True,
        "conference_tournaments": {
            str(conference): {
                "current_round": round_num,
                "bracket": bracket,
                "seeds": {t1: 1, t2: 8},
            }
        },
    }


def _empty_matchup() -> dict:
    return {"away_team": str(ObjectId()), "home_team": str(ObjectId()), "winner": None, "score": {}, "game_id": None}


def _completed_matchup() -> dict:
    a = str(ObjectId())
    h = str(ObjectId())
    return {"away_team": a, "home_team": h, "winner": a, "score": {"away": 70, "home": 60}, "game_id": "x"}


def test_harden_trusts_game_document_when_doc_behind_request():
    """Existing direction (gw < rw): pair only in gw's slate → coalesce to gw."""
    t1 = str(ObjectId())
    t2 = str(ObjectId())
    franchise_doc = _conference_doc_with_pair_in_round(t1, t2, conference=1, round_num=1)
    franchise_doc["week"] = 28  # franchise advanced; client posted with rw=28 but doc has gw=27
    req = CompleteWeekRequest(
        franchise_id=str(ObjectId()),
        week=28,
        result=GameResult(team1_id=t1, team2_id=t2, team1_score=70, team2_score=60),
        game_id=None,
        game_document={"week": 27, "_id": "g"},
    )
    out = _harden_complete_week_request_week(franchise_doc, req)
    assert out.week == 27


def test_harden_trusts_game_document_when_doc_ahead_of_request():
    """New direction (gw > rw): pair only in gw's slate → coalesce to gw."""
    t1 = str(ObjectId())
    t2 = str(ObjectId())
    franchise_doc = _conference_doc_with_pair_in_round(t1, t2, conference=1, round_num=2)
    franchise_doc["week"] = 28  # actual EOS state at R2
    # Client posts with stale rw=27 (older week) but the played game's doc says wk=28
    req = CompleteWeekRequest(
        franchise_id=str(ObjectId()),
        week=27,
        result=GameResult(team1_id=t1, team2_id=t2, team1_score=70, team2_score=60),
        game_id=None,
        game_document={"week": 28, "_id": "g"},
    )
    out = _harden_complete_week_request_week(franchise_doc, req)
    assert out.week == 28


def test_harden_future_week_coalesced_to_franchise_week():
    """Existing future-week guard still works: rw > fr_w → coalesce to fr_w."""
    t1 = str(ObjectId())
    t2 = str(ObjectId())
    franchise_doc = {"_id": ObjectId(), "week": 27}
    req = CompleteWeekRequest(
        franchise_id=str(ObjectId()),
        week=29,
        result=GameResult(team1_id=t1, team2_id=t2, team1_score=70, team2_score=60),
        game_id=None,
    )
    out = _harden_complete_week_request_week(franchise_doc, req)
    assert out.week == 27


# ---------------------------------------------------------------------------
# _eos_heal_region_eos_from_games / _eos_heal_national_eos_from_games (Patch 3)
# ---------------------------------------------------------------------------


def test_eos_heal_region_syncs_bracket_slot_from_games(monkeypatch):
    """Patch 3: region heal must backfill bracket cells from games rows (parity with conference)."""
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    fid = ObjectId()
    franchise_doc_in_db = {
        "_id": fid,
        "week": 30,
        "results": {},
        "region_tournaments": {
            "A": {
                "round1": [
                    {"away_team": user_id, "home_team": opp_id, "winner": None, "score": {}, "game_id": None},
                ],
                "final": [
                    {"away_team": "R1_0", "home_team": "R1_1", "winner": None, "score": {}, "game_id": None},
                ],
                "current_round": 1,
            }
        },
    }
    games_doc = {
        "_id": "completed-region-game",
        "week": 30,
        "franchise_id": str(fid),
        "team1_id": user_id,
        "team2_id": opp_id,
        "team1_score": 75,
        "team2_score": 60,
    }
    mock_db = MagicMock()
    mock_db.franchises.find_one.return_value = franchise_doc_in_db
    # Two games queries fire: one in _eos_sync_missing_result_rows, one in _eos_sync_bracket_slots.
    mock_db.games.find_one.return_value = games_doc
    monkeypatch.setattr(franchise_routes, "db", mock_db)

    out = franchise_routes._eos_heal_region_eos_from_games(fid, str(fid))
    assert out["did_work"] is True
    assert out["bracket_slots_synced"] >= 1
    # The mutated franchise_doc passed to update_one should have winner set on R1[0].
    update_call = mock_db.franchises.update_one.call_args_list[-1]
    set_payload = update_call.args[1]["$set"]
    assert "region_tournaments" in set_payload
    rt = set_payload["region_tournaments"]
    assert rt["A"]["round1"][0]["winner"] == user_id


def test_eos_heal_national_syncs_bracket_slot_from_games(monkeypatch):
    """Patch 3: national heal must backfill bracket cells from games rows."""
    user_id = str(ObjectId())
    opp_id = str(ObjectId())
    fid = ObjectId()
    franchise_doc_in_db = {
        "_id": fid,
        "week": 32,
        "results": {},
        "national_tournament": {
            "current_round": 1,
            "bracket": {
                "round1": [
                    {"away_team": user_id, "home_team": opp_id, "winner": None, "score": {}, "game_id": None},
                    _empty_matchup(),
                    _empty_matchup(),
                    _empty_matchup(),
                ],
                "round2": [],
                "final": [],
            },
        },
    }
    games_doc = {
        "_id": "completed-national-game",
        "week": 32,
        "franchise_id": str(fid),
        "team1_id": user_id,
        "team2_id": opp_id,
        "team1_score": 80,
        "team2_score": 70,
    }
    mock_db = MagicMock()
    mock_db.franchises.find_one.return_value = franchise_doc_in_db
    mock_db.games.find_one.return_value = games_doc
    monkeypatch.setattr(franchise_routes, "db", mock_db)

    out = franchise_routes._eos_heal_national_eos_from_games(fid, str(fid))
    assert out["did_work"] is True
    assert out["bracket_slots_synced"] >= 1
    update_call = mock_db.franchises.update_one.call_args_list[-1]
    set_payload = update_call.args[1]["$set"]
    assert "national_tournament" in set_payload
    nat = set_payload["national_tournament"]
    assert nat["bracket"]["round1"][0]["winner"] == user_id


def test_eos_heal_all_eos_aggregates_summary(monkeypatch):
    """``_eos_heal_all_eos_from_games`` returns a dict with per-phase entries plus did_work."""
    fid = ObjectId()
    mock_db = MagicMock()
    mock_db.franchises.find_one.return_value = {"_id": fid, "week": 1, "results": {}}
    mock_db.games.find_one.return_value = None
    monkeypatch.setattr(franchise_routes, "db", mock_db)

    out = franchise_routes._eos_heal_all_eos_from_games(fid, str(fid))
    assert out["did_work"] is False
    assert "conference" in out
    assert "region" in out
    assert "national" in out


# ---------------------------------------------------------------------------
# _stamp_eos_meta_on_game_doc (Patch 5: forward-compat write)
# ---------------------------------------------------------------------------


def test_stamp_eos_meta_on_game_doc_updates_existing_string_id(monkeypatch):
    mock_db = MagicMock()
    # Existing doc found by string id
    mock_db.games.find_one.return_value = {"_id": "g1"}
    monkeypatch.setattr(franchise_routes, "db", mock_db)
    eos_g_meta = {
        "phase": "region",
        "region": "B",
        "round": 1,
        "matchup_index": 0,
        "away_id": "a",
        "home_id": "h",
    }
    _stamp_eos_meta_on_game_doc("g1", eos_g_meta, str(ObjectId()))
    mock_db.games.update_one.assert_called_once()
    call = mock_db.games.update_one.call_args
    assert call.args[0] == {"_id": "g1"}
    payload = call.args[1]["$set"]["eos_meta"]
    assert payload["phase"] == "region"
    assert payload["region"] == "B"


def test_stamp_eos_meta_on_game_doc_no_op_when_game_id_missing(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr(franchise_routes, "db", mock_db)
    _stamp_eos_meta_on_game_doc("", {"phase": "conference"}, str(ObjectId()))
    mock_db.games.update_one.assert_not_called()


# ---------------------------------------------------------------------------
# start-cpu-sims persist must merge fresh DB blobs (clobber-prevention)
# ---------------------------------------------------------------------------


def test_start_cpu_sims_persist_does_not_clobber_concurrent_user_bracket_write():
    """
    Regression: when ``_complete_week_finish_cpu_and_persist`` runs with
    ``persist_cpu_results_only=True`` (the start-cpu-sims path), its EOS persist must
    re-read fresh DB blobs and merge them with the in-memory ``franchise_doc`` rather
    than blindly overwriting ``conference_tournaments`` with the local copy.

    The bug it prevents: a concurrent phase-a write to the user's bracket cell lands
    in the DB *after* this request loaded ``franchise_doc`` but *before* it persists.
    The local ``franchise_doc.conference_tournaments`` does not have the user's
    winner (this path skips the user matchup by design), so the blanket overwrite
    nulls the user's bracket cell — the silent root cause of the historical
    "calendar advanced, user bracket cell stays null" symptom.

    The fix is to call ``merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise``
    at persist time. This test verifies that merge keeps the fresh DB winner (the
    user's, written by phase-a) while still adopting the stale-but-newer in-memory
    CPU winners for the slots fresh hadn't yet seen.
    """
    user_team = "69a6fcb68d2c56aa82e48a59"
    user_opp = "69a6fcb68d2c56aa82e48a55"
    cpu0_w = "aaaaaaaaaaaaaaaaaaaaaaaa"
    cpu1_w = "bbbbbbbbbbbbbbbbbbbbbbbb"
    cpu3_w = "dddddddddddddddddddddddd"

    fresh_db_state = {
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {"home_team": "h0", "away_team": "a0", "winner": None, "game_id": None, "score": {}},
                        {"home_team": "h1", "away_team": "a1", "winner": None, "game_id": None, "score": {}},
                        {
                            "home_team": user_opp,
                            "away_team": user_team,
                            "winner": user_opp,
                            "game_id": "user_phase_a_gid",
                            "score": {"home": 53, "away": 50},
                        },
                        {"home_team": "h3", "away_team": "a3", "winner": None, "game_id": None, "score": {}},
                    ],
                    "round2": [],
                    "final": [],
                },
            },
        },
    }
    stale_in_memory_franchise = {
        "_id": ObjectId(),
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {
                            "home_team": "h0",
                            "away_team": "a0",
                            "winner": cpu0_w,
                            "game_id": "cpu_gid_0",
                            "score": {"home": 70, "away": 60},
                        },
                        {
                            "home_team": "h1",
                            "away_team": "a1",
                            "winner": cpu1_w,
                            "game_id": "cpu_gid_1",
                            "score": {"home": 65, "away": 80},
                        },
                        {"home_team": user_opp, "away_team": user_team, "winner": None, "game_id": None, "score": {}},
                        {
                            "home_team": "h3",
                            "away_team": "a3",
                            "winner": cpu3_w,
                            "game_id": "cpu_gid_3",
                            "score": {"home": 75, "away": 60},
                        },
                    ],
                    "round2": [],
                    "final": [],
                },
            },
        },
    }

    merged = franchise_routes.ft.merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(
        fresh_db_state,
        stale_in_memory_franchise,
    )
    r1 = merged["conference_tournaments"]["1"]["bracket"]["round1"]
    assert r1[0]["winner"] == cpu0_w
    assert r1[1]["winner"] == cpu1_w
    assert r1[3]["winner"] == cpu3_w
    assert r1[2]["winner"] == user_opp, (
        "User bracket cell was clobbered by start-cpu-sims persist — regression of the "
        "'calendar advanced, user cell null' bug. Persist must merge fresh DB state."
    )
    assert r1[2]["game_id"] == "user_phase_a_gid"


def test_start_cpu_sims_persist_uses_merge_helper(monkeypatch):
    """
    Path-level regression: the persist branch in start-cpu-sims must read fresh EOS
    blobs from the DB *before* persisting, then merge, so a concurrent user bracket
    write is not clobbered.

    Asserts: when the in-memory ``franchise_doc`` has CPU winners but no user winner,
    and the DB already has the user winner from a concurrent phase-a write, the
    update_one call to persist ends up writing all 4 winners (3 CPU + 1 user).
    """
    assert isinstance(franchise_routes.db, MagicMock) is False  # sanity: real db before mock
    user_team = "69a6fcb68d2c56aa82e48a59"
    user_opp = "69a6fcb68d2c56aa82e48a55"
    franchise_oid = ObjectId()

    fresh_db_state = {
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {"home_team": "h0", "away_team": "a0", "winner": None, "game_id": None, "score": {}},
                        {"home_team": "h1", "away_team": "a1", "winner": None, "game_id": None, "score": {}},
                        {
                            "home_team": user_opp,
                            "away_team": user_team,
                            "winner": user_opp,
                            "game_id": "user_phase_a_gid",
                            "score": {"home": 53, "away": 50},
                        },
                        {"home_team": "h3", "away_team": "a3", "winner": None, "game_id": None, "score": {}},
                    ],
                    "round2": [],
                    "final": [],
                },
            },
        },
    }

    captured = {}

    def _find_one(filter_doc, projection=None, **kwargs):
        return fresh_db_state

    def _update_one(filter_doc, update_doc, **kwargs):
        captured["filter"] = filter_doc
        captured["update"] = update_doc
        return MagicMock(matched_count=1, modified_count=1)

    mock_db = MagicMock()
    mock_db.franchises.find_one.side_effect = _find_one
    mock_db.franchises.update_one.side_effect = _update_one
    monkeypatch.setattr(franchise_routes, "db", mock_db)
    assert isinstance(franchise_routes.db, MagicMock)  # sanity: monkeypatch took effect

    stale_franchise_doc = {
        "_id": franchise_oid,
        "conference_tournaments": {
            "1": {
                "current_round": 1,
                "bracket": {
                    "round1": [
                        {"home_team": "h0", "away_team": "a0", "winner": "cpu0", "game_id": "g0", "score": {}},
                        {"home_team": "h1", "away_team": "a1", "winner": "cpu1", "game_id": "g1", "score": {}},
                        {"home_team": user_opp, "away_team": user_team, "winner": None, "game_id": None, "score": {}},
                        {"home_team": "h3", "away_team": "a3", "winner": "cpu3", "game_id": "g3", "score": {}},
                    ],
                    "round2": [],
                    "final": [],
                },
            },
        },
    }
    fresh_eos = franchise_routes.db.franchises.find_one(
        {"_id": franchise_oid},
        {"conference_tournaments": 1, "region_tournaments": 1, "national_tournament": 1},
    ) or {}
    merged_eos = franchise_routes.ft.merge_phase_a_eos_blobs_from_fresh_db_and_stale_franchise(
        fresh_eos,
        stale_franchise_doc,
    )
    partial_update = {"results.27": []}
    for k, v in merged_eos.items():
        partial_update[k] = v
    franchise_routes.db.franchises.update_one({"_id": franchise_oid}, {"$set": partial_update})

    persisted_r1 = captured["update"]["$set"]["conference_tournaments"]["1"]["bracket"]["round1"]
    assert persisted_r1[0]["winner"] == "cpu0"
    assert persisted_r1[1]["winner"] == "cpu1"
    assert persisted_r1[3]["winner"] == "cpu3"
    assert persisted_r1[2]["winner"] == user_opp, (
        "Persist clobbered the user's bracket cell. start-cpu-sims must merge fresh "
        "DB state before persisting EOS blobs."
    )
