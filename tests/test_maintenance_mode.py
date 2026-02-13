from fastapi.testclient import TestClient

from BackEnd.api import api


client = TestClient(api.app)


def test_maintenance_mode_allows_health(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    res = client.get("/health")
    assert res.status_code == 200


def test_maintenance_mode_blocks_mutations(monkeypatch):
    monkeypatch.setenv("MAINTENANCE_MODE", "true")
    res = client.post("/api/simulate-quarter", json={})
    assert res.status_code == 503
    assert res.json().get("error") == "maintenance_mode"
    assert res.headers.get("retry-after") == "60"

