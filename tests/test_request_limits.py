"""Request body cap (413), input-free 422s, and the removed unauthenticated game routes."""
from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from BackEnd.api.api import app
from BackEnd.utils.request_limits import (
    DEFAULT_MAX_REQUEST_BYTES,
    RequestSizeLimitMiddleware,
    max_request_bytes,
)

client = TestClient(app)
PHASE_A = "/franchise/complete-week/phase-a"
ALLOWED_ORIGIN = "https://gob-test.netlify.app"


def _phase_a_body(target_bytes: int) -> bytes:
    """A phase-a POST shaped like the real one (franchise_id, week, game_id, result,
    game_document with players / teams / box rows), padded to ``target_bytes``."""
    players = []
    body = {
        "franchise_id": "f" * 24,  # no such franchise: the handler answers 404 after reading it
        "week": 25,
        "game_id": "a" * 24,
        "result": {"team1_id": "b" * 24, "team2_id": "c" * 24, "team1_score": 71, "team2_score": 68},
        "game_document": {"_id": "a" * 24, "is_final": True, "quarter": 4, "players": players,
                          "teams": {}, "score": {"Home": 68, "Away": 71}},
    }
    i = 0
    while len(json.dumps(body)) < target_bytes:
        players.append({
            "player_id": f"{i:024x}", "name": f"Player {i}", "team": "Home" if i % 2 else "Away",
            "stats": {"game": {"PTS": i % 30, "REB": i % 12, "AST": i % 9, "FGM": i % 11, "FGA": i % 19,
                               "3PM": i % 5, "3PA": i % 9, "FTM": i % 7, "FTA": i % 8, "MIN": 24}},
            "attributes": {k: 40 + (i % 50) for k in ("SC", "SH", "ID", "OD", "PS", "BH", "RB", "AG", "ST", "ND", "IQ", "FT")},
        })
        i += 1
    return json.dumps(body).encode()


def test_limit_defaults_to_1_mib_and_is_env_overridable():
    assert DEFAULT_MAX_REQUEST_BYTES == 1024 * 1024
    assert max_request_bytes({}) == DEFAULT_MAX_REQUEST_BYTES
    assert max_request_bytes({"GOB_MAX_REQUEST_BYTES": "2097152"}) == 2 * 1024 * 1024
    assert max_request_bytes({"GOB_MAX_REQUEST_BYTES": "junk"}) == DEFAULT_MAX_REQUEST_BYTES
    assert max_request_bytes({"GOB_MAX_REQUEST_BYTES": "0"}) == DEFAULT_MAX_REQUEST_BYTES


def test_oversize_content_length_is_413_before_the_app_runs():
    body = b'{"junk": "' + b"x" * (DEFAULT_MAX_REQUEST_BYTES + 10) + b'"}'
    res = client.post(PHASE_A, content=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert res.json() == {"detail": "Request body too large"}


def test_oversize_streamed_body_is_413():
    chunk = b"x" * 65536

    def stream():
        yield b'{"junk": "'
        for _ in range(DEFAULT_MAX_REQUEST_BYTES // len(chunk) + 4):
            yield chunk
        yield b'"}'

    res = client.post(PHASE_A, content=stream(), headers={"Content-Type": "application/json"})
    assert res.status_code == 413
    assert res.json() == {"detail": "Request body too large"}


def test_413_carries_cors_headers():
    body = b"x" * (DEFAULT_MAX_REQUEST_BYTES + 1)
    res = client.post(PHASE_A, content=body,
                      headers={"Content-Type": "application/json", "Origin": ALLOWED_ORIGIN})
    assert res.status_code == 413
    assert res.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


@pytest.mark.parametrize("size", [130_000, DEFAULT_MAX_REQUEST_BYTES - 4096])
def test_real_sized_phase_a_body_reaches_the_handler(size):
    # 130 KB = the largest phase-a body measured on gob-staging (report); the second
    # case is just under the cap.
    body = _phase_a_body(size)
    assert size <= len(body) < DEFAULT_MAX_REQUEST_BYTES
    res = client.post(PHASE_A, content=body, headers={"Content-Type": "application/json"})
    # Parsed and validated, then the handler ran: the made-up franchise is not found.
    assert res.status_code == 404, res.text


def test_middleware_caps_streamed_reads_for_any_handler():
    tiny = FastAPI()

    @tiny.post("/echo")
    async def echo(request: Request):  # reads the raw body, no model
        return {"n": len(await request.body())}

    tiny.add_middleware(RequestSizeLimitMiddleware, max_bytes=100)
    c = TestClient(tiny)
    assert c.post("/echo", content=b"x" * 100).json() == {"n": 100}
    assert c.post("/echo", content=b"x" * 101).status_code == 413
    assert c.post("/echo", content=iter([b"x" * 60, b"x" * 60])).status_code == 413


def test_422_keeps_loc_msg_type_and_never_echoes_input():
    marker = "ECHO-ME-" * 500
    res = client.post(PHASE_A, json={"franchise_id": "f" * 24, "result": {"team1_id": marker}})
    assert res.status_code == 422
    assert marker not in res.text
    assert '"input"' not in res.text
    detail = res.json()["detail"]
    assert detail and all(set(item) == {"loc", "msg", "type"} for item in detail)
    locs = {tuple(item["loc"]) for item in detail}
    assert ("body", "week") in locs
    assert all(item["msg"] and item["type"] for item in detail)


@pytest.mark.parametrize("method,path", [("GET", "/games"), ("POST", "/api/simulate"), ("POST", "/simulate")])
def test_unauthenticated_game_routes_are_gone(method, path):
    res = client.request(method, path, json={"home_team": "A", "away_team": "B"})
    assert res.status_code in (404, 405)
