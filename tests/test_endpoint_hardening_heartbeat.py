"""Endpoint hardening + CPU-week claim heartbeat.

- removed routes 404 (run_training, sentry-debug, debug/server-state, debug-names)
- diagnostics dumps are 200 {}/no-write unless GOB_DIAGNOSTICS_ENABLED=1
- API docs off in production only
- global exception handler: no exception text; origin reflected only if allowlisted
- claim heartbeat: advances while held, stops after release, owner-only, still blocks
  a second acquirer; same on mongomock and SQLite
"""

import time
import uuid
from pathlib import Path

import pytest
from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient

from BackEnd.api import _bootstrap, api, franchise_routes
from BackEnd.env_config import resolve_database_environment
from BackEnd.persistence import create_store

client = TestClient(api.app)


# --- removed routes ------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/api/run_training"),
        ("get", "/sentry-debug"),
        ("get", "/debug/server-state"),
        ("get", "/franchise/debug-names"),
    ],
)
def test_removed_routes_404(method, path):
    kwargs = {"json": {"team_name": "X", "session_type": "s", "allocations": {}}} if method == "post" else {}
    res = getattr(client, method)(path, **kwargs)
    if path == "/franchise/debug-names":
        # DELETE /franchise/{franchise_id} matches the path, so Starlette answers a
        # GET with 405 rather than 404: there is no GET handler left either way.
        assert res.status_code in (404, 405)
    else:
        assert res.status_code == 404


def test_removed_routes_not_registered():
    paths = {getattr(r, "path", None) for r in api.app.routes}
    for gone in ("/api/run_training", "/sentry-debug", "/debug/server-state", "/franchise/debug-names"):
        assert gone not in paths


# --- diagnostics gate -------------------------------------------------------------

_SIM_Q = {
    "gameId": "g1", "quarter": 1, "homeTeam": "H", "awayTeam": "A",
    "timestamp": "2026-09-29T12:00:00Z",
    "scoreIncrements": [], "printedEvents": [], "mismatches": [],
    "totalScoreIncrements": 0, "totalPrintedEvents": 0, "mismatchCount": 0,
}
_FT_FG = {
    "gameId": "g1", "quarter": 1, "homeTeam": "H", "awayTeam": "A",
    "timestamp": "2026-09-29T12:00:00Z",
    "freeThrowEvents": [], "madeFGEvents": [], "printedFTEvents": [], "printedMadeFGEvents": [],
    "ftMismatches": [], "fgMismatches": [],
    "totalFreeThrows": 0, "totalMadeFGs": 0, "totalPrintedFTs": 0, "totalPrintedMadeFGs": 0,
    "ftMismatchCount": 0, "fgMismatchCount": 0,
}
_DIAG = [("/api/diagnostics/sim-quarter", _SIM_Q), ("/api/diagnostics/ft-fg-analysis", _FT_FG)]


def _written(tmp_path: Path) -> list:
    d = tmp_path / "docs" / "0_Text_Scroll_Debug"
    return list(d.iterdir()) if d.exists() else []


@pytest.mark.parametrize("path,body", _DIAG)
def test_diagnostics_off_by_default_returns_empty_json_and_writes_nothing(path, body, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GOB_DIAGNOSTICS_ENABLED", raising=False)
    res = client.post(path, json=body)
    assert res.status_code == 200
    assert res.json() == {}
    assert _written(tmp_path) == []
    assert not (tmp_path / "docs").exists()


@pytest.mark.parametrize("path,body", _DIAG)
def test_diagnostics_work_when_enabled(path, body, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GOB_DIAGNOSTICS_ENABLED", "1")
    res = client.post(path, json=body)
    assert res.status_code == 200
    assert res.json().get("filename")
    assert len(_written(tmp_path)) == 1


# --- API docs -------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_disabled_in_production(path):
    app = FastAPI(**_bootstrap._docs_kwargs({"ENVIRONMENT": "production"}))
    assert TestClient(app).get(path).status_code == 404


@pytest.mark.parametrize("env", ["development", "staging"])
@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_docs_enabled_outside_production(env, path):
    app = FastAPI(**_bootstrap._docs_kwargs({"ENVIRONMENT": env}))
    assert TestClient(app).get(path).status_code == 200


# --- global exception handler -----------------------------------------------------


@pytest.fixture
def boom_path():
    path = f"/__test_boom_{uuid.uuid4().hex[:8]}"

    def _boom():
        raise RuntimeError("secret-internal-detail mongodb://user:pw@host")

    api.app.add_api_route(path, _boom, methods=["GET"])
    try:
        yield path
    finally:
        api.app.router.routes[:] = [r for r in api.app.router.routes if getattr(r, "path", None) != path]


def _boom_client():
    return TestClient(api.app, raise_server_exceptions=False)


def test_exception_handler_hides_exception_text(boom_path):
    res = _boom_client().get(boom_path)
    assert res.status_code == 500
    body = res.json()
    assert body["error"] == "Internal server error"
    assert body["error_id"]
    text = res.text
    assert "secret-internal-detail" not in text
    assert "RuntimeError" not in text
    assert set(body) == {"error", "error_id"}


def test_exception_handler_logs_full_exception_with_error_id(boom_path, caplog):
    res = _boom_client().get(boom_path)
    error_id = res.json()["error_id"]
    logged = [r for r in caplog.records if error_id in r.getMessage()]
    assert logged and logged[0].exc_info and "secret-internal-detail" in str(logged[0].exc_info[1])


def test_exception_handler_does_not_reflect_disallowed_origin(boom_path):
    res = _boom_client().get(boom_path, headers={"Origin": "https://evil.example.com"})
    assert res.status_code == 500
    assert "access-control-allow-origin" not in {k.lower() for k in res.headers}


def test_exception_handler_reflects_allowlisted_origin(boom_path):
    allowed = api.cors_origins[0]
    res = _boom_client().get(boom_path, headers={"Origin": allowed})
    assert res.status_code == 500
    assert res.headers.get("access-control-allow-origin") == allowed
    assert res.headers.get("access-control-allow-credentials") == "true"


# --- CPU-week claim heartbeat ------------------------------------------------------


@pytest.fixture(params=["mongomock", "sqlite"])
def claim_db(request, tmp_path, monkeypatch):
    store = None
    if request.param == "sqlite":
        env = resolve_database_environment(
            pristine_env={
                "GOB_DB_MODE": "mongomock",
                "ENVIRONMENT": "test",
                "MONGO_DB_NAME": "gob-test",
                "GOB_PERSISTENCE": "sqlite",
                "GOB_SQLITE_PATH": str(tmp_path / "save.sqlite"),
            },
            repo_root=tmp_path,
            target_environ={},
        )
        store = create_store(env)
        monkeypatch.setattr(franchise_routes, "db", store.db)
    monkeypatch.setattr(franchise_routes, "_CPU_SIM_CLAIM_HEARTBEAT_SECONDS", 0.05)
    fid = franchise_routes.db.franchises.insert_one({"week": 3}).inserted_id
    yield fid
    if store is not None:
        store.client.close()


def _claim(fid, week=3):
    doc = franchise_routes.db.franchises.find_one({"_id": fid}) or {}
    return ((doc.get("cpu_sim_jobs") or {}).get(str(week)) or {}).get("claim") or {}


def _wait_for(pred, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(0.02)
    return False


def test_heartbeat_advances_while_claim_held_and_stops_after_release(claim_db):
    fid = claim_db
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-a")
    first = _claim(fid)["heartbeat"]
    hb = franchise_routes._CpuSimClaimHeartbeat(fid, 3, "owner-a").start()
    try:
        assert _wait_for(lambda: _claim(fid)["heartbeat"] > first)
    finally:
        hb.stop()
        franchise_routes._release_cpu_sim_claim(fid, 3, "owner-a")
    assert not hb._thread.is_alive()
    after_release = _claim(fid)["heartbeat"]
    time.sleep(0.25)
    assert _claim(fid)["heartbeat"] == after_release
    assert _claim(fid)["active"] is False


def test_non_owner_cannot_refresh_heartbeat(claim_db):
    fid = claim_db
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-a")
    before = _claim(fid)["heartbeat"]
    time.sleep(0.01)
    assert franchise_routes._refresh_cpu_sim_claim_heartbeat(fid, 3, "intruder") is False
    assert _claim(fid)["heartbeat"] == before
    assert franchise_routes._refresh_cpu_sim_claim_heartbeat(fid, 3, "owner-a") is True


def test_refresher_stops_itself_when_claim_is_no_longer_owned(claim_db):
    fid = claim_db
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-a")
    hb = franchise_routes._CpuSimClaimHeartbeat(fid, 3, "owner-a").start()
    try:
        franchise_routes._release_cpu_sim_claim(fid, 3, "owner-a")
        assert _wait_for(lambda: not hb._thread.is_alive())
    finally:
        hb.stop()


def test_second_acquirer_refused_while_heartbeat_fresh_past_stale_window(claim_db, monkeypatch):
    """A claim acquired more than the stale window ago stays owned while refreshed."""
    fid = claim_db
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-a")
    # Backdate acquire + heartbeat beyond the 300s stale threshold (a slow week).
    old = "2000-01-01T00:00:00Z"
    path = franchise_routes._cpu_sim_claim_path(3)
    franchise_routes.db.franchises.update_one(
        {"_id": fid}, {"$set": {f"{path}.acquired_at": old, f"{path}.heartbeat": old}}
    )
    hb = franchise_routes._CpuSimClaimHeartbeat(fid, 3, "owner-a").start()
    try:
        assert _wait_for(lambda: _claim(fid)["heartbeat"] > old)
        assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-b") is False
        assert _claim(fid)["owner"] == "owner-a"
    finally:
        hb.stop()
        franchise_routes._release_cpu_sim_claim(fid, 3, "owner-a")
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-b") is True


def test_stale_claim_without_heartbeat_is_still_reclaimable(claim_db):
    """Crash backstop unchanged: no refresher -> stale after 300s -> re-claimable."""
    fid = claim_db
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-a")
    path = franchise_routes._cpu_sim_claim_path(3)
    franchise_routes.db.franchises.update_one(
        {"_id": fid}, {"$set": {f"{path}.heartbeat": "2000-01-01T00:00:00Z"}}
    )
    assert franchise_routes._CPU_SIM_CLAIM_STALE_SECONDS == 90
    assert franchise_routes._acquire_cpu_sim_claim(fid, 3, "owner-b") is True
