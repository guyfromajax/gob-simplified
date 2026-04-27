from bson import ObjectId

from BackEnd.api import gameplan_routes


class _FakeFTDCollection:
    """Minimal FTD for strategy merge tests."""

    def __init__(self, row):
        self._row = row

    def find_one(self, query, projection=None):
        if query.get("franchise_id") == self._row.get("franchise_id") and query.get("team_id") == self._row.get("team_id"):
            return self._row
        return None


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


def test_get_gameplan_franchise_resolves_team_by_canonical_when_name_mismatch(monkeypatch):
    """Name on game snapshot may not match franchise user_team_id string; ObjectId → canonical still finds row."""
    franchise_id = "507f1f77bcf86cd799439021"
    game_id = "game-789"
    team_object_id = "507f1f77bcf86cd799439022"
    canonical_team_id = "MORRISTOWN"

    franchise_doc = {
        "_id": ObjectId(franchise_id),
        "user_team_id": "Morristown",
        "user_team_object_id": ObjectId(team_object_id),
    }

    game_strategy_settings = {
        "offense": 0,
        "inside": 3,
        "attack": 0,
        "outside": 0,
        "tempo": 2,
        "defense": 2,
        "aggression": 2,
        "hc_trap": 2,
        "fc_press": 2,
        "rebounding": 2,
    }

    game_doc = {
        "_id": game_id,
        "mode": "franchise",
        "franchise_id": franchise_id,
        "teams": {
            canonical_team_id: {
                "name": "Stale Or Wrong Label",
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
    monkeypatch.setattr(
        gameplan_routes,
        "unified_resolve_team_id_to_canonical",
        lambda team_identifier, mode="single", doc=None: canonical_team_id,
    )

    response = gameplan_routes.get_gameplan(
        mode="franchise",
        team_id=team_object_id,
        franchise_id=franchise_id,
        game_id=game_id,
    )

    assert response["strategy_settings"].get("inside") == 3


def test_get_gameplan_franchise_merges_ftd_strategy_when_game_snapshot_empty(monkeypatch):
    franchise_id = "507f1f77bcf86cd799439031"
    game_id = "game-ftd-merge"
    team_object_id = "507f1f77bcf86cd799439032"
    canonical_team_id = "MORRISTOWN"

    franchise_doc = {
        "_id": ObjectId(franchise_id),
        "user_team_id": "Morristown",
        "user_team_object_id": ObjectId(team_object_id),
    }

    ftd_strategy = {
        "offense": 1,
        "inside": 4,
        "attack": 1,
        "outside": 1,
        "tempo": 2,
        "defense": 2,
        "aggression": 3,
        "hc_trap": 2,
        "fc_press": 2,
        "rebounding": 2,
    }

    game_doc = {
        "_id": game_id,
        "mode": "franchise",
        "franchise_id": franchise_id,
        "teams": {
            canonical_team_id: {
                "name": "Morristown",
                "strategy_settings": {},
            }
        },
    }

    fake_collection = _FakeCollection(franchise_doc)
    fake_games_collection = _FakeGamesCollection(game_id, game_doc)
    fake_ftd = _FakeFTDCollection(
        {
            "franchise_id": ObjectId(franchise_id),
            "team_id": ObjectId(team_object_id),
            "strategy_settings": ftd_strategy,
        }
    )

    monkeypatch.setattr(gameplan_routes, "games_collection", fake_games_collection)
    monkeypatch.setattr(gameplan_routes, "franchise_team_data_collection", fake_ftd)
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

    assert response["strategy_settings"].get("inside") == 4
    assert response["strategy_settings"].get("aggression") == 3


def test_gm_playbook_non_empty_detects_pc_order_and_set_plays():
    from BackEnd.utils.shared import _gm_playbook_non_empty_for_summarize

    assert _gm_playbook_non_empty_for_summarize({}) is False
    assert _gm_playbook_non_empty_for_summarize({"pc_order": {"offense": ["a"], "defense": []}}) is True
    assert _gm_playbook_non_empty_for_summarize({"set_plays": {"x": 10}}) is True
