"""Deferred-offseason apply (Defer_Offseason_To_Camp_Plan.md).

The offseason develop_rollover was moved out of finish_season into the Week-1 TC training
path via `_apply_deferred_offseason`. These pin the helper's contract: it faithfully applies
develop_rollover (values equal a direct call with the same seed — the relocation changes
WHEN, not WHAT), develops in place, and is deterministic per (player, season) so a pre-persist
retry reproduces the same result.
"""
import copy
import logging
import random

logging.disable(logging.CRITICAL)

from BackEnd.utils import player_development as dev
from BackEnd.api.franchise_routes import _apply_deferred_offseason

CORE = list(dev.GROWTH_ATTRS)


def _fpd_doc(pos="C", tier="Average", seed=3, year="Sophomore", pid="p1"):
    """FPD-shaped doc as finish_season leaves it: year advanced, carried dev fields,
    UN-developed attributes (the deferred-develop input)."""
    rng = random.Random(seed)
    player, profile = dev.init_career(pos, tier, 50, rng)
    return {
        "franchise_id": "f", "player_id": pid,
        "meta": {"first_name": "A", "last_name": "B", "year": year,
                 "height": player["height"], "weight": player["weight"]},
        "attributes": dict(player["attributes"]),
        "position_ratings": dict(player["position_ratings"]),
        "entry_tier": tier, "position_intent": pos, "training_position": pos,
        "potential_factor": 1.0, "development": profile,
    }


def _sum12(a):
    return sum(a.get(f"anchor_{x}", a.get(x, 0)) for x in CORE)


def test_helper_develops_in_place_and_reports():
    doc = _fpd_doc()
    before = _sum12(doc["attributes"])
    reports = _apply_deferred_offseason([doc], season=2)
    assert _sum12(doc["attributes"]) > before, "offseason rescale should raise attributes"
    assert len(reports) == 1
    r = reports[0]
    assert r["player_id"] == "p1"
    assert r["rt_after"] >= r["rt_before"]
    # dev fields written back onto the doc
    assert "development" in doc and doc.get("entry_tier")


def test_helper_deterministic_per_player_season():
    d1, d2 = _fpd_doc(pid="x"), _fpd_doc(pid="x")
    _apply_deferred_offseason([d1], season=2)
    _apply_deferred_offseason([d2], season=2)
    assert d1["attributes"] == d2["attributes"], "same (player, season) must reproduce exactly"


def test_helper_faithfully_applies_develop_rollover():
    """Relocation changes WHEN, not WHAT: the helper's result equals a direct
    develop_rollover call seeded the same way (offseason:<pid>:<season>)."""
    doc = _fpd_doc(pid="z", year="Junior")
    doc_copy = copy.deepcopy(doc)
    _apply_deferred_offseason([doc], season=5)
    rng = random.Random("offseason:z:5")
    out = dev.develop_rollover(doc_copy, "Junior", rng, season_allocation=None)
    assert doc["attributes"] == out["attributes"]
    assert doc["meta"]["height"] == out["height"]


def test_helper_handles_recruit_jh_to_fr():
    """A signed recruit rolls JH→Freshman at TC (finish_season advanced the year label)."""
    doc = _fpd_doc(pos="SG", year="Freshman", pid="rec1")
    before = _sum12(doc["attributes"])
    reports = _apply_deferred_offseason([doc], season=2)
    assert _sum12(doc["attributes"]) >= before
    assert reports[0]["year"] == "Freshman"


# ── Integration: finish_season DEFERS (producer side) ─────────────────────────
from types import SimpleNamespace
from unittest.mock import MagicMock
from bson import ObjectId
from BackEnd.api import franchise_routes
from BackEnd.models import franchise_manager


def test_finish_season_defers_develop_and_arms_marker(monkeypatch):
    """finish_season must NOT develop (develop_rollover never called) and MUST persist
    offseason_dev_pending_season = next_season on the new FTD. Guards the enumerated-$set
    trap: a state-dict-only marker would silently never reach the FTD."""
    franchise_id = ObjectId()
    team_id = ObjectId()
    inserted_docs: list = []
    ftd_update_calls: list = []

    mock_franchises = MagicMock()
    mock_franchises.find_one.return_value = {
        "_id": franchise_id, "week": 36, "current_season": 1, "results": {},
        "week_35_recruiting_results": {"signed_players": [{
            "player_id": "sign-1", "team_id": str(team_id), "team_name": "Town",
            "name": "Deferred Guy", "height": 77, "weight": 201, "jersey": 11,
            "archetype": "Outside C", "year": "JH",
            "attributes": {"SC": 3, "SH": 2, "ID": 3, "OD": 1, "PS": 0, "BH": 3,
                           "RB": 2, "ST": 6, "AG": 3, "ND": 0, "IQ": 1, "FT": 2},
            "position_ratings": {"C": 40, "PF": 30},
        }]},
    }
    mock_franchises.update_one = MagicMock(return_value=SimpleNamespace(modified_count=1))
    monkeypatch.setattr(franchise_routes, "db",
                        SimpleNamespace(franchises=mock_franchises, games=MagicMock()))

    def _cap_ftd_update(*a, **k):
        ftd_update_calls.append((a, k))
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", MagicMock(
        find=MagicMock(return_value=[{"franchise_id": franchise_id, "team_id": team_id, "players": []}]),
        update_one=MagicMock(side_effect=_cap_ftd_update),
    ))
    mock_fpd = MagicMock(find=MagicMock(return_value=[]), delete_many=MagicMock())
    mock_fpd.insert_many.side_effect = lambda docs: inserted_docs.extend(docs)
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", mock_fpd)
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection",
                        MagicMock(delete_many=MagicMock(), insert_many=MagicMock()))
    monkeypatch.setattr(franchise_manager, "FranchiseManager", lambda _db: SimpleNamespace(
        schedule_manager=SimpleNamespace(generate_schedule=lambda: []),
        recruit_manager=SimpleNamespace(generate_recruits_list=lambda count=300: []),
        _build_region_team_map=lambda: {"A": []}))
    monkeypatch.setattr(franchise_routes.Player, "randomize_game_attributes",
                        staticmethod(lambda attrs, *, preserve_character=False: attrs))

    # finish_season must NOT call develop — blow up loudly if it does.
    def _boom(*a, **k):
        raise AssertionError("finish_season must not call develop_rollover (deferred to TC)")
    monkeypatch.setattr("BackEnd.utils.player_development.develop_rollover", _boom)

    result = franchise_routes.finish_season(
        franchise_routes.FinishSeasonRequest(franchise_id=str(franchise_id)))
    assert result["status"] == "success"

    # 1) persisted attributes are UN-developed (raw signed values)
    doc = next(d for d in inserted_docs if d["player_id"] == "sign-1")
    assert doc["attributes"]["SC"] == 3 and doc["attributes"]["anchor_SC"] == 3
    assert doc["meta"]["year"] == "Freshman"  # year DID advance (JH→FR)

    # 2) marker armed to next_season (=2) in a persisted FTD $set
    marker_writes = [
        call for call in ftd_update_calls
        if (call[0][1] if len(call[0]) > 1 else {}).get("$set", {}).get("offseason_dev_pending_season") == 2
    ]
    assert marker_writes, (
        "offseason_dev_pending_season=2 was not persisted to any FTD $set — the marker "
        "never reaches the DB and the Week-1 develop would never fire.")

    # 3) offseason report is NOT revealed at finish (deferred to TC)
    assert result.get("offseason_development") == []


# ── Integration: Week-1 training CONSUMES the deferred offseason (consumer side) ──
def _fpd_full(pid="ret-1", year="Sophomore"):
    """FPD doc as it sits between finish_season and TC: year advanced, un-developed."""
    d = _fpd_doc(pos="C", tier="Average", seed=7, year=year, pid=pid)
    d["meta"]["team_id"] = None
    for a in CORE:                      # ensure all 12 present as anchors
        d["attributes"].setdefault(a, 50)
        d["attributes"].setdefault(f"anchor_{a}", d["attributes"][a])
    d["attributes"].setdefault("CH", 55); d["attributes"].setdefault("anchor_CH", 55)
    return d


def _run_consumer(monkeypatch, *, marker, current_season, week=1):
    """Drive _run_franchise_training_impl at `week` with execute_training mocked, returning
    (result, ftd_update_calls, fpd_update_calls)."""
    fid = ObjectId(); tid = ObjectId()
    fpd = _fpd_full()
    ftd_calls = []; fpd_calls = []

    franchise_doc = {
        "_id": fid, "week": week, "current_season": current_season,
        "training_status": {}, "results": {},
        "user_team_id": "Town", "user_team_object_id": str(tid),
    }
    monkeypatch.setattr(franchise_routes, "db", SimpleNamespace(
        franchises=MagicMock(find_one=MagicMock(return_value=franchise_doc), update_one=MagicMock()),
        teams=MagicMock(find_one=MagicMock(return_value={"_id": tid, "player_ids": ["ret-1"]})),
        players=MagicMock(find=MagicMock(return_value=[]), find_one=MagicMock(return_value={"height": 80})),
    ))
    ftd_doc = {"franchise_id": str(fid), "team_id": tid, "players": ["ret-1"]}
    if marker is not None:
        ftd_doc["offseason_dev_pending_season"] = marker
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", MagicMock(
        find_one=MagicMock(return_value=ftd_doc),
        update_one=MagicMock(side_effect=lambda *a, **k: ftd_calls.append((a, k))),
    ))
    monkeypatch.setattr(franchise_routes, "franchise_players_data_collection", MagicMock(
        find=MagicMock(return_value=[fpd]),
        update_one=MagicMock(side_effect=lambda *a, **k: fpd_calls.append((a, k))),
    ))
    monkeypatch.setattr(franchise_routes, "_training_report_recruiting_display",
                        lambda *a, **k: None)
    # Satisfy the exact-budget guard without hand-building a 30/24-point allocation
    # (impl imports training_points_spent from the source module at call time).
    monkeypatch.setattr("BackEnd.constants.training_shape.training_points_spent",
                        lambda *a, **k: 30 if week == 1 else 24)

    def fake_execute_training(players, team, allocations, coaching_focus, **kw):
        # bypass the camp engine — just echo players so the consumer wiring is what's tested
        return players, team, kw.get("plays_data"), kw.get("scouting_data"), {
            "player_changes": {}, "team_changes": {}, "coaching_focus": {},
        }
    monkeypatch.setattr("BackEnd.models.training_execution_v2.execute_training",
                        fake_execute_training)

    req = franchise_routes.FranchiseTrainingRequest(
        franchise_id=str(fid),
        training_data={"player_drills": {}, "team_drills": {}, "general": {}, "coaching_focus": None},
    )
    result = franchise_routes._run_franchise_training_impl(req, phase="user_only")
    return result, ftd_calls, fpd_calls


def _marker_cleared(ftd_calls):
    for a, _k in ftd_calls:
        setdoc = (a[1] if len(a) > 1 else {}).get("$set", {})
        if "offseason_dev_pending_season" in setdoc and setdoc["offseason_dev_pending_season"] is None:
            return True
    return False


def test_week1_consumes_offseason_when_marker_armed(monkeypatch):
    result, ftd_calls, fpd_calls = _run_consumer(monkeypatch, marker=2, current_season=2)
    assert result["status"] == "success"
    # develop ran → an offseason report row surfaced in the response
    assert result.get("offseason_development"), "offseason not developed/revealed at Week-1"
    assert result["offseason_development"][0]["player_id"] == "ret-1"
    # marker disarmed in a persisted FTD $set
    assert _marker_cleared(ftd_calls), "offseason_dev_pending_season was not cleared"


def test_week1_noop_when_no_marker(monkeypatch):
    result, ftd_calls, fpd_calls = _run_consumer(monkeypatch, marker=None, current_season=2)
    assert result["status"] == "success"
    assert result.get("offseason_development") == [], "developed despite no armed marker"


def test_week2_never_consumes_offseason(monkeypatch):
    # marker armed but it's not camp week → must not develop
    result, ftd_calls, fpd_calls = _run_consumer(monkeypatch, marker=2, current_season=2, week=2)
    assert result.get("offseason_development") == [], "developed outside Week-1 camp"
