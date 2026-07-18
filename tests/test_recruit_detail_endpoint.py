from bson import ObjectId
from fastapi.testclient import TestClient

from BackEnd.api.api import app
import BackEnd.api.franchise_routes as franchise_routes


client = TestClient(app)

# Mirrors the real schema: teams._id is an ObjectId, while FRD's Lean stores its
# STRING form. A mock with string _ids hides the type mismatch that shipped a raw
# id to the UI, so these ids are ObjectIds on purpose.
LEAN_TEAM_OID = ObjectId("69a6fcb68d2c56aa82e48abd")


def _matches(doc, query):
    for k, v in query.items():
        if k == "$or":
            if not any(_matches(doc, sub) for sub in v):
                return False
        elif doc.get(k) != v:
            return False
    return True


class _MockCollection:
    def __init__(self, docs):
        self.docs = docs

    def find_one(self, query, projection=None):
        for doc in self.docs:
            if _matches(doc, query):
                out = dict(doc)
                if projection:
                    for key, include in projection.items():
                        if not include:
                            out.pop(key, None)
                return out
        return None


class _MockDb:
    def __init__(self, teams, franchises=None):
        self.teams = _MockCollection(teams)
        self.franchises = _MockCollection(franchises if franchises is not None else [])


FRANCHISE_OID = ObjectId("6a5b8beb332cb691f1fa043b")
FRANCHISE_ID = str(FRANCHISE_OID)

RECRUIT = {
    "_id": "mongo1",
    "franchise_id": FRANCHISE_ID,
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
    # Lean holds the string form of an ObjectId, as the real FRD docs do.
    "Lean": {"1": str(LEAN_TEAM_OID), "2": None, "3": None},
}


def _patch(monkeypatch, recruits, teams=None, franchises=None):
    monkeypatch.setattr(
        franchise_routes,
        "franchise_recruits_data_collection",
        _MockCollection(recruits),
    )
    monkeypatch.setattr(
        franchise_routes,
        "db",
        _MockDb(
            teams if teams is not None else [{"_id": LEAN_TEAM_OID, "name": "Seattle AAA"}],
            franchises=franchises if franchises is not None else [{"_id": FRANCHISE_OID}],
        ),
    )


def test_recruit_endpoint_returns_recruit(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    resp = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Test Recruit"
    assert data["image_id"] == "img1"
    assert data["is_recruit"] is True
    assert data["attributes"]["SC"] == 80
    assert data["position_ratings"]["PG"] == 92
    assert data["is_signed"] is False
    # projection strips mongo internals
    assert "_id" not in data
    assert "franchise_id" not in data


def test_recruit_endpoint_surfaces_ps_stats_as_season(monkeypatch):
    """Practice-squad stats live at FRD.ps_season_stats; the player page's stats
    renderer reads `season`. The endpoint bridges the two."""
    recruit = dict(RECRUIT, ps_season_stats={"PTS": 42, "FGM": 15, "FGA": 30, "GP": 4})
    _patch(monkeypatch, [recruit])

    resp = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["season"]["PTS"] == 42
    assert data["season"]["FGM"] == 15
    assert data["ps_season_stats"]["GP"] == 4


def test_recruit_endpoint_season_empty_when_never_played(monkeypatch):
    """ps_season_stats is created lazily on first PS game, so absent is normal."""
    _patch(monkeypatch, [RECRUIT])

    data = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}").json()
    assert data["season"] == {}


def test_recruit_endpoint_resolves_lean_team_name(monkeypatch):
    """Lean stores a stringified ObjectId; the page must show the team NAME."""
    _patch(monkeypatch, [RECRUIT])

    data = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}").json()
    assert data["lean_display"] == "Seattle AAA"
    # Regression: a {"_id": <str>} lookup misses (teams._id is an ObjectId) and
    # used to fall back to echoing the raw id into the UI.
    assert data["lean_display"] != str(LEAN_TEAM_OID)


def test_recruit_endpoint_lean_never_leaks_raw_id(monkeypatch):
    """If the team can't be resolved, show '--' rather than a raw id."""
    _patch(monkeypatch, [RECRUIT], teams=[])

    data = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}").json()
    assert str(LEAN_TEAM_OID) not in data["lean_display"]


def test_recruit_endpoint_open_lean(monkeypatch):
    recruit = dict(RECRUIT, Lean={"1": "open", "2": None, "3": None})
    _patch(monkeypatch, [recruit])

    data = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}").json()
    assert data["lean_display"] == "Open"


def test_recruit_endpoint_signed_after_week_35(monkeypatch):
    """After week-35 recruiting, detail page shows signed school (not lean)."""
    franchises = [
        {
            "_id": FRANCHISE_OID,
            "week_35_recruiting_ran": True,
            "week_35_recruiting_results": {
                "signed_by_recruit_id": {
                    "r1": {
                        "team_id": str(LEAN_TEAM_OID),
                        "team_name": "Xavien Prep",
                        "walk_on": False,
                    }
                }
            },
        }
    ]
    _patch(monkeypatch, [RECRUIT], franchises=franchises)

    data = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}").json()
    assert data["is_signed"] is True
    assert data["signed_team_name"] == "Xavien Prep"
    assert data["signed_display"] == "Xavien Prep"
    # Lean still resolved for older clients / debugging, but UI prefers signed.
    assert data["lean_display"] == "Seattle AAA"


def test_recruit_endpoint_signed_walk_on_suffix(monkeypatch):
    franchises = [
        {
            "_id": FRANCHISE_OID,
            "week_35_recruiting_ran": True,
            "week_35_recruiting_results": {
                "signed_by_recruit_id": {
                    "r1": {
                        "team_id": str(LEAN_TEAM_OID),
                        "team_name": "Xavien Prep",
                        "walk_on": True,
                    }
                }
            },
        }
    ]
    _patch(monkeypatch, [RECRUIT], franchises=franchises)

    data = client.get(f"/recruit/r1?franchise_id={FRANCHISE_ID}").json()
    assert data["signed_display"] == "Xavien Prep (walk on)"


def test_recruit_endpoint_unknown_recruit_404(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    assert client.get(f"/recruit/nope?franchise_id={FRANCHISE_ID}").status_code == 404


def test_recruit_endpoint_scoped_to_franchise(monkeypatch):
    """recruit_id is only unique within a franchise; a wrong franchise must not
    leak another franchise's recruit."""
    _patch(monkeypatch, [RECRUIT])

    assert client.get("/recruit/r1?franchise_id=other").status_code == 404


def test_recruit_endpoint_requires_franchise_id(monkeypatch):
    _patch(monkeypatch, [RECRUIT])

    assert client.get("/recruit/r1").status_code == 422
