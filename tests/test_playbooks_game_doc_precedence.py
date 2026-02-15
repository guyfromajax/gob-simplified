import pytest
from bson import ObjectId

from BackEnd.api import gameplan_routes


class _FakeCollection:
    def __init__(self, franchise_doc):
        self._franchise_doc = franchise_doc
        self.name = "franchises"

    def find_one(self, query, projection=None):
        # Master/franchise document lookups
        if query.get("_id") == self._franchise_doc["_id"]:
            return self._franchise_doc
        return None

    def update_one(self, query, update, upsert=False):
        class _Result:
            matched_count = 1
            modified_count = 1
            upserted_id = None

        return _Result()


class _FakeGamesCollection:
    def __init__(self, game_id, game_doc):
        self._game_id = game_id
        self._game_doc = game_doc

    def find_one(self, query, projection=None):
        query_id = query.get("_id")
        if query_id == self._game_id:
            return self._game_doc
        return None


class _FakeGamesCollectionObjectIdOnly:
    """Fake that only matches when _id is looked up as ObjectId (simulates real MongoDB)."""

    def __init__(self, game_id_str, game_doc):
        self._game_id_str = game_id_str
        self._game_doc = game_doc

    def find_one(self, query, projection=None):
        query_id = query.get("_id")
        if query_id == self._game_id_str:
            return None  # String lookup fails (as when DB has ObjectId)
        try:
            if isinstance(query_id, ObjectId) and str(query_id) == str(self._game_id_str):
                return self._game_doc
            if str(query_id) == str(self._game_id_str):
                return self._game_doc
        except Exception:
            pass
        return None

    def update_one(self, query, update, upsert=False):
        """No-op for tests; handler may call this when ensuring position_filters/plays on game doc."""
        class _Result:
            matched_count = 1
            modified_count = 1
        return _Result()


def test_get_playbooks_prefers_game_doc_for_franchise_when_game_id_present(monkeypatch):
    franchise_id = "507f1f77bcf86cd799439011"
    game_id = "game-123"
    team_object_id = "507f1f77bcf86cd799439012"
    canonical_team_id = "MORRISTOWN"

    franchise_doc = {
        "_id": ObjectId(franchise_id),
        "user_team_id": "Morristown",
        "user_team_object_id": ObjectId(team_object_id),
    }

    game_playbook_settings = {
        "motion": {"4-1 Motion": 77},
        "set_play_inside": {},
        "set_play_attack": {},
        "set_play_outside": {},
        "zone_defense": {},
        "man_defense": {},
        "slot_assignments": {"1": {"section": "motion", "playId": "4-1 Motion"}},
        "motion_dropdowns": {},
        "position_filters": {"standard": ["standard"], "PG": [], "SG": [], "SF": [], "PF": [], "C": []},
        "_meta": {"seed_version": "alpha_v1", "user_saved": False},
    }

    game_doc = {
        "_id": game_id,
        "mode": "franchise",
        "franchise_id": franchise_id,
        "teams": {
            canonical_team_id: {
                "name": "Morristown",
                "playbook_settings": game_playbook_settings,
                "plays": {
                    "4-1 Motion": {"play_type": "motion", "play_focus": "inside", "play_id": "p1"}
                },
            }
        },
    }

    fake_collection = _FakeCollection(franchise_doc)
    fake_games_collection = _FakeGamesCollection(game_id, game_doc)

    monkeypatch.setattr(gameplan_routes, "games_collection", fake_games_collection)
    monkeypatch.setattr(gameplan_routes, "get_collection_and_doc_id", lambda mode, franchise_id, tournament_id, game_id: (fake_collection, franchise_id))
    monkeypatch.setattr(gameplan_routes, "get_user_team_from_franchise", lambda doc: ("Morristown", team_object_id))

    response = gameplan_routes.get_playbooks(
        mode="franchise",
        team_id=team_object_id,
        franchise_id=franchise_id,
        game_id=game_id,
    )

    motion_percentages = response["playbook_percentages"]["motion"]
    assert motion_percentages.get("4-1 Motion") == 77
    assert response["slot_assignments"].get("1", {}).get("playId") == "4-1 Motion"
    assert response["playbook_meta"] == {"seed_version": "alpha_v1", "user_saved": False}


def test_get_playbooks_franchise_with_objectid_game_id_returns_game_doc(monkeypatch):
    """When game doc is stored with ObjectId _id, backend should find it via ObjectId(game_id) fallback."""
    franchise_id = "507f1f77bcf86cd799439011"
    game_id_str = "507f1f77bcf86cd799439099"
    team_object_id = "507f1f77bcf86cd799439012"
    canonical_team_id = "MORRISTOWN"

    franchise_doc = {
        "_id": ObjectId(franchise_id),
        "user_team_id": "Morristown",
        "user_team_object_id": ObjectId(team_object_id),
    }

    game_playbook_settings = {
        "slot_assignments": {"1": {"section": "set_play_inside", "playId": "Base Post Play"}},
        "motion": {},
        "set_play_inside": {},
        "set_play_attack": {},
        "set_play_outside": {},
        "zone_defense": {},
        "man_defense": {},
        "motion_dropdowns": {},
        "position_filters": {"standard": [], "PG": [], "SG": [], "SF": [], "PF": [], "C": []},
    }

    game_doc = {
        "_id": ObjectId(game_id_str),
        "mode": "franchise",
        "franchise_id": franchise_id,
        "teams": {
            canonical_team_id: {
                "name": "Morristown",
                "playbook_settings": game_playbook_settings,
                "plays": {"Base Post Play": {"play_type": "set_play", "play_focus": "inside"}},
            }
        },
    }

    fake_collection = _FakeCollection(franchise_doc)
    fake_games = _FakeGamesCollectionObjectIdOnly(game_id_str, game_doc)

    monkeypatch.setattr(gameplan_routes, "games_collection", fake_games)
    monkeypatch.setattr(
        gameplan_routes,
        "get_collection_and_doc_id",
        lambda mode, franchise_id, tournament_id, game_id: (fake_collection, franchise_id),
    )
    monkeypatch.setattr(
        gameplan_routes, "get_user_team_from_franchise", lambda doc: ("Morristown", team_object_id)
    )

    response = gameplan_routes.get_playbooks(
        mode="franchise",
        team_id=team_object_id,
        franchise_id=franchise_id,
        game_id=game_id_str,
    )

    assert response["slot_assignments"].get("1", {}).get("playId") == "Base Post Play"


def test_save_playbooks_marks_meta_user_saved(monkeypatch):
    captured = {}

    def _fake_save_team_settings(**kwargs):
        captured.update(kwargs)
        return True, "MORRISTOWN", "franchises"

    monkeypatch.setattr("BackEnd.utils.team_settings_manager.save_team_settings", _fake_save_team_settings)

    request = gameplan_routes.PlaybookSettingsRequest(
        mode="franchise",
        team_id="MORRISTOWN",
        franchise_id="507f1f77bcf86cd799439011",
        playbook_settings={
            "motion": {"4-1 Motion": 100},
            "_meta": {"seed_version": "alpha_v1", "user_saved": False},
        },
    )

    response = gameplan_routes.save_playbooks(request)

    assert response["success"] is True
    assert captured["settings_data"]["_meta"]["seed_version"] == "alpha_v1"
    assert captured["settings_data"]["_meta"]["user_saved"] is True


@pytest.mark.integration
def test_get_playbooks_franchise_with_game_id_returns_game_doc_slot_assignments():
    """
    Integration: GET /api/playbooks with mode=franchise, franchise_id, team_id, game_id
    must return slot_assignments from the game document (not FTD).
    """
    from fastapi.testclient import TestClient
    from BackEnd.api.api import app
    from BackEnd.db import games_collection, franchises_collection, franchise_team_data_collection

    client = TestClient(app)
    franchise_id = ObjectId()
    user_team_object_id = ObjectId()
    game_oid = ObjectId()

    franchise_doc = {
        "_id": franchise_id,
        "user_team_id": "South Lancaster",
        "user_team_object_id": user_team_object_id,
    }

    ftd_slots = {"1": {"section": "motion", "playId": "4-1 Motion"}}
    game_slots = {"1": {"section": "set_play_inside", "playId": "Base Post Play"}, "2": {"section": "motion", "playId": "5-0 Motion"}}

    game_doc = {
        "_id": game_oid,
        "mode": "franchise",
        "franchise_id": franchise_id,
        "quarter": 1,
        "teams": {
            "SOUTH_LANCASTER": {
                "name": "South Lancaster",
                "playbook_settings": {
                    "slot_assignments": game_slots,
                    "motion": {},
                    "set_play_inside": {},
                    "set_play_attack": {},
                    "set_play_outside": {},
                    "zone_defense": {},
                    "man_defense": {},
                    "motion_dropdowns": {},
                    "position_filters": {"standard": [], "PG": [], "SG": [], "SF": [], "PF": [], "C": []},
                },
                "plays": {"Base Post Play": {}, "5-0 Motion": {}, "4-1 Motion": {}},
            }
        },
    }

    franchises_collection.insert_one(franchise_doc)
    franchise_team_data_collection.insert_one({
        "franchise_id": franchise_id,
        "team_id": user_team_object_id,
        "playbook_settings": {"slot_assignments": ftd_slots},
        "plays": {},
    })
    games_collection.insert_one(game_doc)

    try:
        r = client.get(
            "/api/playbooks",
            params={
                "mode": "franchise",
                "team_id": str(user_team_object_id),
                "franchise_id": str(franchise_id),
                "game_id": str(game_oid),
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        slot_assignments = data.get("slot_assignments") or {}
        assert slot_assignments.get("1", {}).get("playId") == "Base Post Play", (
            "Expected slot 1 from game doc (Base Post Play), got %s" % slot_assignments
        )
        assert slot_assignments.get("2", {}).get("playId") == "5-0 Motion", (
            "Expected slot 2 from game doc (5-0 Motion), got %s" % slot_assignments
        )
    finally:
        franchises_collection.delete_one({"_id": franchise_id})
        franchise_team_data_collection.delete_many({"franchise_id": franchise_id})
        games_collection.delete_one({"_id": game_oid})
