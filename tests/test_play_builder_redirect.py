"""Play Builder V1 was deleted (2026-10-01). Its path must land on V2."""
from fastapi.testclient import TestClient

from starlette.requests import Request

from BackEnd.api.api import app
from BackEnd.api.play_routes import STATIC_DIR, redirect_play_builder_v1

client = TestClient(app)


def test_v1_path_redirects_to_v2_and_keeps_the_query():
    res = client.get("/play-builder.html?play_id=abc", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/play-builder-v2.html?play_id=abc"


def test_v1_path_without_a_query_redirects_to_v2():
    res = client.get("/play-builder.html", follow_redirects=False)
    assert res.status_code == 301
    assert res.headers["location"] == "/play-builder-v2.html"


def test_v2_is_still_served_and_v1_file_is_gone():
    res = client.get("/play-builder-v2.html")
    assert res.status_code == 200
    assert not (STATIC_DIR / "play-builder.html").exists()
    assert not (STATIC_DIR / "homepage-v3.html").exists()


def test_router_redirect_used_on_hosted_environments():
    """Hosted API has no local static middleware, so the router answers the path itself."""
    scope = {"type": "http", "method": "GET", "path": "/play-builder.html", "query_string": b"play_id=abc",
             "headers": [], "server": ("testserver", 80), "scheme": "http"}
    res = redirect_play_builder_v1(Request(scope))
    assert res.status_code == 301
    assert res.headers["location"] == "/play-builder-v2.html?play_id=abc"
