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
