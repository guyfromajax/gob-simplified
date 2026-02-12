from fastapi.testclient import TestClient

from BackEnd.api.api import app
import BackEnd.api.api as api_module


client = TestClient(app)


class _MockCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                if projection:
                    out = {}
                    for key, include in projection.items():
                        if include and key in doc:
                            out[key] = doc[key]
                    return out
                return dict(doc)
        return None


def test_player_endpoint_default_universal_data(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "players_collection",
        _MockCollection(
            [
                {
                    "_id": "p1",
                    "first_name": "Test",
                    "last_name": "Player",
                    "attributes": {"SC": 80},
                    "position_ratings": {"PG": 92},
                }
            ]
        ),
    )
    monkeypatch.setattr(
        api_module,
        "franchise_players_data_collection",
        _MockCollection([]),
    )

    resp = client.get("/player/p1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["first_name"] == "Test"
    assert data["attributes"]["SC"] == 80
    assert data["position_ratings"]["PG"] == 92


def test_player_endpoint_franchise_overlay(monkeypatch):
    monkeypatch.setattr(
        api_module,
        "players_collection",
        _MockCollection(
            [
                {
                    "_id": "p2",
                    "first_name": "Mode",
                    "last_name": "Aware",
                    "year": "freshman",
                    "attributes": {"SC": 70},
                    "position_ratings": {"SG": 85},
                }
            ]
        ),
    )
    monkeypatch.setattr(
        api_module,
        "franchise_players_data_collection",
        _MockCollection(
            [
                {
                    "franchise_id": "f123",
                    "player_id": "p2",
                    "attributes": {"SC": 95},
                    "position_ratings": {"SG": 98},
                    "meta": {"year": "junior"},
                }
            ]
        ),
    )

    resp = client.get("/player/p2?mode=franchise&franchise_id=f123")
    assert resp.status_code == 200
    data = resp.json()
    assert data["attributes"]["SC"] == 95
    assert data["position_ratings"]["SG"] == 98
    assert data["year"] == "junior"
