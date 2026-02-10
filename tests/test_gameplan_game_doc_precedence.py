from bson import ObjectId

from BackEnd.api import gameplan_routes


class _FakeCollection:
    def __init__(self, franchise_doc):
        self._franchise_doc = franchise_doc
        self.name = "franchises"

    def find_one(self, query, projection=None):
        if query.get("_id") == self._franchise_doc["_id"]:
            return self._franchise_doc
        return None


class _FakeGamesCollection:
    def __init__(self, game_id, game_doc):
        self._game_id = game_id
        self._game_doc = game_doc

    def find_one(self, query, projection=None):
        if query.get("_id") == self._game_id:
            return self._game_doc
        return None


def test_get_gameplan_prefers_game_doc_for_franchise_when_game_id_present(monkeypatch):
    franchise_id = "507f1f77bcf86cd799439021"
    game_id = "game-456"
    team_object_id = "507f1f77bcf86cd799439022"
    canonical_team_id = "MORRISTOWN"

    franchise_doc = {
        "_id": ObjectId(franchise_id),
        "user_team_id": "Morristown",
        "user_team_object_id": ObjectId(team_object_id),
    }

    game_strategy_settings = {
        "offense": 1,
        "inside": 4,
        "attack": 1,
        "outside": 0,
        "tempo": 3,
        "defense": 3,
        "aggression": 4,
        "hc_trap": 1,
        "fc_press": 1,
        "rebounding": 2,
    }

    game_doc = {
        "_id": game_id,
        "mode": "franchise",
        "franchise_id": franchise_id,
        "teams": {
            canonical_team_id: {
                "name": "Morristown",
                "strategy_settings": game_strategy_settings,
            }
        },
    }

    fake_collection = _FakeCollection(franchise_doc)
    fake_games_collection = _FakeGamesCollection(game_id, game_doc)

    monkeypatch.setattr(gameplan_routes, "games_collection", fake_games_collection)
    monkeypatch.setattr(
        gameplan_routes,
        "get_collection_and_doc_id",
        lambda mode, franchise_id, tournament_id, game_id: (fake_collection, franchise_id),
    )
    monkeypatch.setattr(gameplan_routes, "get_user_team_from_franchise", lambda doc: ("Morristown", team_object_id))

    response = gameplan_routes.get_gameplan(
        mode="franchise",
        team_id=team_object_id,
        franchise_id=franchise_id,
        game_id=game_id,
    )

    strategy = response["strategy_settings"]
    assert strategy.get("inside") == 4
    assert strategy.get("aggression") == 4
    assert strategy.get("tempo") == 3
