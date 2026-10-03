"""Deploys must not strand in-flight week advances.

- claim stale window: 90 s (3 missed 30 s heartbeats), env-overridable, floored
- shutdown hook releases ONLY this process's claims, stops heartbeats, idempotent
- pools: shutdown terminates live executors and never falls back to in-process sims
- simulated mid-advance restart: a dead owner's claim blocks only until stale (or
  until our own shutdown hook released it); phase-b then completes and every
  matchup is written exactly once
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api import franchise_routes as fr
from BackEnd.api.api import app
from BackEnd.db import db
from BackEnd.utils import cpu_week_pool
from tests.test_franchise_complete_week import _fake_franchise_cpu_full_sim, setup_franchise

client = TestClient(app)


def _ip() -> dict:
    """A unique client IP per request: the week-advance limit (10/min) is keyed per
    IP for tokenless calls, and these tests must not spend the shared "testclient"
    budget other complete-week tests depend on."""
    import uuid
    n = uuid.uuid4().int
    return {"X-Real-IP": f"198.18.{n % 250}.{(n >> 8) % 250 + 1}"}


@pytest.fixture(autouse=True)
def _clean_state():
    fr._owned_claims.clear()
    cpu_week_pool._shutdown_event.clear()
    cpu_week_pool._live_executors.clear()
    yield
    fr._owned_claims.clear()
    cpu_week_pool._shutdown_event.clear()
    cpu_week_pool._live_executors.clear()


def _iso_ago(seconds: float) -> str:
    return (datetime.utcnow() - timedelta(seconds=seconds)).isoformat() + "Z"


def _plant_claim(fid, week: int, owner: str, heartbeat_age_s: float) -> None:
    db.franchises.update_one({"_id": ObjectId(str(fid))}, {"$set": {fr._cpu_sim_claim_path(week): {
        "active": True, "owner": owner, "acquired_at": _iso_ago(heartbeat_age_s + 60),
        "heartbeat": _iso_ago(heartbeat_age_s)}}})


def _claim(fid, week: int) -> dict:
    doc = db.franchises.find_one({"_id": ObjectId(str(fid))}) or {}
    return ((doc.get("cpu_sim_jobs") or {}).get(str(week)) or {}).get("claim") or {}


# --- stale window ---------------------------------------------------------------


@pytest.mark.parametrize("raw,expected", [(None, 90), ("120", 120), ("10", 90), ("junk", 90), ("", 90)])
def test_stale_window_default_override_and_floor(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("GOB_CPU_SIM_CLAIM_STALE_SECONDS", raising=False)
    else:
        monkeypatch.setenv("GOB_CPU_SIM_CLAIM_STALE_SECONDS", raw)
    assert fr._cpu_sim_claim_stale_seconds() == expected


def test_module_default_is_90_seconds():
    assert fr._CPU_SIM_CLAIM_STALE_SECONDS == 90
    assert fr._CPU_SIM_CLAIM_STALE_SECONDS >= 3 * fr._CPU_SIM_CLAIM_HEARTBEAT_SECONDS
    assert fr._CPU_SIM_CLAIM_WAIT_SECONDS > fr._CPU_SIM_CLAIM_STALE_SECONDS  # phase-b outlasts a dead owner


def test_claim_without_heartbeat_for_over_90s_is_reclaimable():
    fid, _ = setup_franchise()
    oid = ObjectId(fid)
    _plant_claim(fid, 1, "dead-process", heartbeat_age_s=91)
    assert fr._acquire_cpu_sim_claim(oid, 1, "new-owner") is True
    assert _claim(fid, 1)["owner"] == "new-owner"


def test_claim_with_live_heartbeat_is_not_reclaimable():
    fid, _ = setup_franchise()
    oid = ObjectId(fid)
    _plant_claim(fid, 1, "live-owner", heartbeat_age_s=60)
    assert fr._acquire_cpu_sim_claim(oid, 1, "intruder") is False
    assert _claim(fid, 1)["owner"] == "live-owner"


# --- shutdown hook: claims ----------------------------------------------------------


def test_shutdown_releases_only_this_process_claims_and_is_idempotent():
    mine, _ = setup_franchise()
    theirs = str(db.franchises.insert_one({"week": 1}).inserted_id)
    assert fr._acquire_cpu_sim_claim(ObjectId(mine), 1, "owner-mine")
    hb = fr._CpuSimClaimHeartbeat(ObjectId(mine), 1, "owner-mine").start()
    _plant_claim(theirs, 1, "owner-other-process", heartbeat_age_s=5)
    before_other = _claim(theirs, 1)

    assert fr.release_owned_cpu_sim_claims("shutdown") == 1
    assert not hb._thread.is_alive()
    mine_claim = _claim(mine, 1)
    assert mine_claim["active"] is False and mine_claim["released_reason"] == "shutdown"
    assert _claim(theirs, 1) == before_other  # never touch another process's claim

    assert fr.release_owned_cpu_sim_claims("shutdown") == 0  # idempotent
    assert fr._owned_claims == {}


def test_shutdown_does_not_release_a_claim_another_process_took_over():
    fid, _ = setup_franchise()
    oid = ObjectId(fid)
    assert fr._acquire_cpu_sim_claim(oid, 1, "owner-mine")
    # Our claim went stale and another process re-claimed it.
    _plant_claim(fid, 1, "owner-new-deploy", heartbeat_age_s=1)
    assert fr.release_owned_cpu_sim_claims("shutdown") == 0
    assert _claim(fid, 1)["owner"] == "owner-new-deploy" and _claim(fid, 1)["active"] is True


def test_normal_release_unregisters_the_claim():
    fid, _ = setup_franchise()
    assert fr._acquire_cpu_sim_claim(ObjectId(fid), 1, "o1")
    assert (fid, 1, "o1") in fr._owned_claims
    fr._release_cpu_sim_claim(ObjectId(fid), 1, "o1")
    assert fr._owned_claims == {}


# --- shutdown hook: pools ---------------------------------------------------------------


def test_shutdown_all_pools_terminates_live_workers_and_is_idempotent():
    proc = MagicMock()
    ex = MagicMock()
    ex._processes = {1: proc}
    cpu_week_pool._live_executors.add(ex)
    assert cpu_week_pool.shutdown_all_pools() == 1
    ex.shutdown.assert_called_once_with(wait=False, cancel_futures=True)
    proc.terminate.assert_called_once()
    assert cpu_week_pool.shutting_down()
    cpu_week_pool._live_executors.clear()
    assert cpu_week_pool.shutdown_all_pools() == 0


def test_no_new_pool_and_no_inprocess_fallback_once_shutting_down():
    cpu_week_pool.shutdown_all_pools()
    with patch.object(cpu_week_pool, "_run_sequential_inprocess") as seq, \
            patch.object(cpu_week_pool, "ProcessPoolExecutor") as ppe:
        with pytest.raises(cpu_week_pool.ShutdownInProgress):
            cpu_week_pool.simulate_cpu_week_pooled([(0, "f", "h", "a", "H", "A")], max_workers=2)
    ppe.assert_not_called()
    seq.assert_not_called()


def test_app_shutdown_handler_runs_pool_and_claim_release():
    """The registered FastAPI shutdown handler releases our claims and stops pools.

    Called directly rather than via `with TestClient(app)`: entering the app lifespan
    also runs STARTUP, which installs the process-wide RNG draw guard for every test
    that follows (tens of thousands of warnings in the full suite)."""
    fid, _ = setup_franchise()
    assert fr._acquire_cpu_sim_claim(ObjectId(fid), 1, "owner-app")
    handlers = [h for h in app.router.on_shutdown if h.__name__ == "release_cpu_week_work_on_shutdown"]
    assert len(handlers) == 1
    handlers[0]()
    assert _claim(fid, 1)["active"] is False
    assert cpu_week_pool.shutting_down()


def test_startup_clears_the_shutdown_flag():
    cpu_week_pool.shutdown_all_pools()
    assert cpu_week_pool.shutting_down()
    cpu_week_pool.reset_shutdown_state()  # what the app's startup handler calls
    assert not cpu_week_pool.shutting_down()


# --- simulated mid-advance restart -------------------------------------------------------


def _count_calls():
    calls = []

    def fake(*a, **k):
        calls.append(a)
        return _fake_franchise_cpu_full_sim(*a, **k)
    return calls, fake


def _cpu_game_docs(fid, ids) -> int:
    """Game docs for the CPU matchup (C vs D; A vs B is the user's game)."""
    c, d = ids[2], ids[3]
    return db.games.count_documents({"franchise_id": fid, "week": 1, "$or": [
        {"team1_id": c, "team2_id": d}, {"team1_id": d, "team2_id": c},
        {"team1_id": str(c), "team2_id": str(d)}, {"team1_id": str(d), "team2_id": str(c)}]})


def _phase_a(fid):
    payload = {"franchise_id": fid, "week": 1,
               "result": {"team1_id": "A", "team2_id": "B", "team1_score": 70, "team2_score": 60}}
    r = client.post("/franchise/complete-week/phase-a", json=payload, headers=_ip())
    assert r.status_code == 200, r.text


def test_restart_after_cpu_results_persisted_finishes_once(monkeypatch):
    """Old process wrote the CPU results, then died holding the claim (no shutdown hook)."""
    fid, ids = setup_franchise()
    calls, fake = _count_calls()
    with patch.object(fr, "_run_franchise_cpu_full_simulation_core", side_effect=fake):
        assert client.post("/franchise/complete-week/start-cpu-sims", json={"franchise_id": fid, "week": 1}, headers=_ip()).status_code == 200
    assert len(calls) == 1
    cpu_docs_before = _cpu_game_docs(fid, ids)
    assert cpu_docs_before == 1
    _phase_a(fid)
    _plant_claim(fid, 1, "dead-process", heartbeat_age_s=fr._CPU_SIM_CLAIM_STALE_SECONDS + 1)

    with patch.object(fr, "_run_franchise_cpu_full_simulation_core", side_effect=fake):
        rb = client.post("/franchise/complete-week/phase-b", json={"franchise_id": fid, "week": 1}, headers=_ip())
    assert rb.status_code == 200, rb.text
    doc = db.franchises.find_one({"_id": ObjectId(fid)})
    assert doc["week"] == 2
    rows = doc["results"]["1"]
    assert len(rows) == 2
    assert len({frozenset((str(r["away_id"]), str(r["home_id"]))) for r in rows}) == 2  # each matchup once
    assert len(calls) == 1  # CPU game not re-simmed
    assert _cpu_game_docs(fid, ids) == 1  # no duplicate CPU game doc

    rb2 = client.post("/franchise/complete-week/phase-b", json={"franchise_id": fid, "week": 1}, headers=_ip())
    assert rb2.status_code == 200 and rb2.json().get("idempotent") is True


def test_restart_during_pool_resims_the_game_once(monkeypatch):
    """Old process died mid-pool: nothing persisted, matchup left 'running', claim held."""
    fid, _ = setup_franchise()
    _phase_a(fid)
    _plant_claim(fid, 1, "dead-process", heartbeat_age_s=fr._CPU_SIM_CLAIM_STALE_SECONDS + 1)
    calls, fake = _count_calls()
    with patch.object(fr, "_run_franchise_cpu_full_simulation_core", side_effect=fake):
        rb = client.post("/franchise/complete-week/phase-b", json={"franchise_id": fid, "week": 1}, headers=_ip())
    assert rb.status_code == 200, rb.text
    doc = db.franchises.find_one({"_id": ObjectId(fid)})
    assert doc["week"] == 2 and len(doc["results"]["1"]) == 2
    assert len(calls) == 1


def test_live_owner_still_blocks_phase_b(monkeypatch):
    """A healthy owner (fresh heartbeat) is never pre-empted: phase-b waits, then 503."""
    fid, _ = setup_franchise()
    _phase_a(fid)
    _plant_claim(fid, 1, "live-owner", heartbeat_age_s=5)
    monkeypatch.setattr(fr, "_CPU_SIM_CLAIM_WAIT_SECONDS", 1)
    rb = client.post("/franchise/complete-week/phase-b", json={"franchise_id": fid, "week": 1}, headers=_ip())
    assert rb.status_code == 503
    assert _claim(fid, 1)["owner"] == "live-owner"


def test_after_our_shutdown_hook_next_request_reclaims_immediately(monkeypatch):
    """Graceful path: the dying process released its claim, so no stale wait at all."""
    fid, _ = setup_franchise()
    _phase_a(fid)
    assert fr._acquire_cpu_sim_claim(ObjectId(fid), 1, "old-deploy-owner")
    fr.release_owned_cpu_sim_claims("shutdown")
    monkeypatch.setattr(fr, "_CPU_SIM_CLAIM_WAIT_SECONDS", 0)  # must not need to wait at all
    with patch.object(fr, "_run_franchise_cpu_full_simulation_core", side_effect=_fake_franchise_cpu_full_sim):
        rb = client.post("/franchise/complete-week/phase-b", json={"franchise_id": fid, "week": 1}, headers=_ip())
    assert rb.status_code == 200, rb.text
    assert db.franchises.find_one({"_id": ObjectId(fid)})["week"] == 2
