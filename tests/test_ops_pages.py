"""Custom 404 page on HTML requests; API 404s stay JSON."""

from fastapi.testclient import TestClient

from BackEnd.api.api import app

client = TestClient(app)


def test_missing_html_page_returns_branded_404():
    res = client.get("/some-missing-page", headers={"Accept": "text/html"})
    assert res.status_code == 404
    assert "text/html" in (res.headers.get("content-type") or "")
    assert "This page doesn't exist" in res.text
    assert "geekedout_logo.png" in res.text


def test_missing_html_file_returns_branded_404():
    res = client.get("/no-such-view.html", headers={"Accept": "text/html"})
    assert res.status_code == 404
    assert "This page doesn't exist" in res.text


def test_missing_api_route_stays_json_404():
    res = client.get("/api/does-not-exist", headers={"Accept": "text/html,application/json"})
    assert res.status_code == 404
    assert "application/json" in (res.headers.get("content-type") or "")
    body = res.json()
    assert "detail" in body
    assert "This page doesn't exist" not in res.text
