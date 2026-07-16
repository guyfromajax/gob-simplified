from fastapi.testclient import TestClient

from BackEnd.api.api import app
import BackEnd.api.franchise_routes as franchise_routes


client = TestClient(app)


class _MockCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                out = dict(doc)
                if projection:
                    for key, include in projection.items():
                        if not include:
                            out.pop(key, None)
                return out
        return None


class _MockDb:
    def __init__(self, teams):
        self.teams = _MockCollection(teams)


RECRUIT = {
    "_id": "mongo1",
    "franchise_id": "f1",
    "recruit_id": "r1",
    "image_id": "img1",
    "name": "Test Recruit",
    "attributes": {"SC": 80},
    "position_ratings": {"PG": 92},
    "height": 75,
    "weight": 195,
    "archetype": "Slasher",
    "year": "JH",
    "Home Region": "A",
    "Lean": {"1": "MORRISTOWN", "2": None, "3": None},
}


def _patch(monkeypatch, recruits, teams=None):
    monkeypatch.setattr(
        franchise_routes,
        "franchise_recruits_data_collection",
        _MockCollection(recruits),
    )
    monkeypatch.setattr(
        franchise_routes,
        "db",
        _MockDb(teams if teams is not None else [{"_id": "MORRISTOWN", "name": "Morristown"}]),
    )


def test_recruit_endpoint_returns_recruit(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    resp = client.get("/recruit/r1?franchise_id=f1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Recruit"
    assert data["image_id"] == "img1"
    assert data["is_recruit"] is True
    assert data["attributes"]["SC"] == 80
    assert data["position_ratings"]["PG"] == 92
    # projection strips mongo internals
    assert "_id" not in data
    assert "franchise_id" not in data


def test_recruit_endpoint_surfaces_ps_stats_as_season(monkeypatch):
    """Practice-squad stats live at FRD.ps_season_stats; the player page's stats
    renderer reads `season`. The endpoint bridges the two."""
    recruit = dict(RECRUIT, ps_season_stats={"PTS": 42, "FGM": 15, "FGA": 30, "GP": 4})
    _patch(monkeypatch, [recruit])

    resp = client.get("/recruit/r1?franchise_id=f1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["season"]["PTS"] == 42
    assert data["season"]["FGM"] == 15
    assert data["ps_season_stats"]["GP"] == 4


def test_recruit_endpoint_season_empty_when_never_played(monkeypatch):
    """ps_season_stats is created lazily on first PS game, so absent is normal."""
    _patch(monkeypatch, [RECRUIT])

    data = client.get("/recruit/r1?franchise_id=f1").json()
    assert data["season"] == {}


def test_recruit_endpoint_resolves_lean_team_name(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    data = client.get("/recruit/r1?franchise_id=f1").json()
    assert data["lean_display"] == "Morristown"


def test_recruit_endpoint_open_lean(monkeypatch):
    recruit = dict(RECRUIT, Lean={"1": "open", "2": None, "3": None})
    _patch(monkeypatch, [recruit])

    data = client.get("/recruit/r1?franchise_id=f1").json()
    assert data["lean_display"] == "Open"


def test_recruit_endpoint_unknown_recruit_404(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    assert client.get("/recruit/nope?franchise_id=f1").status_code == 404


def test_recruit_endpoint_scoped_to_franchise(monkeypatch):
    """recruit_id is only unique within a franchise; a wrong franchise must not
    leak another franchise's recruit."""
    _patch(monkeypatch, [RECRUIT])

    assert client.get("/recruit/r1?franchise_id=other").status_code == 404


def test_recruit_endpoint_requires_franchise_id(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    assert client.get("/recruit/r1").status_code == 422
