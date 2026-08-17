import pytest
from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)


def test_maintenance_mode_allows_health(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    res = client.get("/health")
    assert res.status_code == 200


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_maintenance_mode_blocks_every_mutating_http_verb(monkeypatch, method):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    res = client.request(method.upper(), "/maintenance-contract-probe", json={})
    assert res.status_code == 503
    assert res.json().get("error") == "maintenance_mode"
    assert res.headers.get("retry-after") == "60"


def test_maintenance_mode_allows_ordinary_gets(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")

    res = client.get("/maintenance-contract-probe")

    # No route owns the probe. Reaching the router's 404 proves middleware did
    # not convert the read into a maintenance response.
    assert res.status_code == 404


def test_disabled_maintenance_mode_restores_mutation_routing(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "false")

    res = client.post("/maintenance-contract-probe", json={})

    assert res.status_code == 404
    assert res.json().get("error") != "maintenance_mode"
