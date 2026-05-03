import pytest
from bson import ObjectId

from BackEnd.api import franchise_routes


class _FakeGamesCollection:
    def __init__(self, game_doc):
        self._game_doc = game_doc

    def find_one(self, query, projection=None):
        if query.get("_id") == self._game_doc.get("_id"):
            return self._game_doc
        return None

    def update_one(self, query, update, upsert=False):
        """Persist eog_inputs merge for tests (franchise_routes.update_team_attributes_after_game)."""
        if query.get("_id") != self._game_doc.get("_id"):
            return None
        payload = (update or {}).get("$set") or {}
        if "eog_inputs" in payload:
            self._game_doc["eog_inputs"] = payload["eog_inputs"]
        return {"matched_count": 1}


class _FakeTeamsCollection:
    def find_one(self, query, projection=None):
        return None


class _FakeDB:
    def __init__(self, game_doc):
        self.games = _FakeGamesCollection(game_doc)
        self.teams = _FakeTeamsCollection()


class _FakeFranchiseTeamDataCollection:
    def __init__(self, franchise_id, home_oid, away_oid):
        self._franchise_id = franchise_id
        self._home_oid = home_oid
        self._away_oid = away_oid
        self.update_calls = []
        self._docs = {
            home_oid: {
                "team_attributes": {
                    "shot_threshold": 100,
                    "discipline": 0,
                    "fight": 0,
                    "rebound_modifier": 0.2,
                    "offensive_efficiency": 0,
                    "defensive_efficiency": 0,
                    "fb_efficiency": 0,
                    "fb_opp_modifier": 0,
                    "pt_efficiency": 0,
                    "pt_opp_modifier": 0,
                    "team_chemistry": 15,
                }
            },
            away_oid: {
                "team_attributes": {
                    "shot_threshold": 100,
                    "discipline": 0,
                    "fight": 0,
                    "rebound_modifier": 0.2,
                    "offensive_efficiency": 0,
                    "defensive_efficiency": 0,
                    "fb_efficiency": 0,
                    "fb_opp_modifier": 0,
                    "pt_efficiency": 0,
                    "pt_opp_modifier": 0,
                    "team_chemistry": 15,
                }
            },
        }

    def find_one(self, query, projection=None):
        if query.get("franchise_id") != self._franchise_id:
            return None
        return self._docs.get(query.get("team_id"))

    def update_one(self, query, update, upsert=False):
        self.update_calls.append((query, update, upsert))
        team_id = query.get("team_id")
        if team_id in self._docs:
            updates = update.get("$set", {})
            for key, value in updates.items():
                if key.startswith("team_attributes."):
                    attr = key.split(".", 1)[1]
                    self._docs[team_id]["team_attributes"][attr] = value


def test_eog_attribute_tuning_ranges_applied(monkeypatch):
    game_id = "game-eog-1"
    franchise_id = ObjectId("507f1f77bcf86cd799439031")
    home_team_id = "HOME_TEAM"
    away_team_id = "AWAY_TEAM"
    home_oid = ObjectId("507f1f77bcf86cd799439032")
    away_oid = ObjectId("507f1f77bcf86cd799439033")

    game_doc = {
        "_id": game_id,
        "box_score": {
            home_team_id: {
                "p1": {"FGM": 60, "FGA": 100, "TO": 10, "STL": 30, "DREB": 30, "OREB": 10}
            },
            away_team_id: {
                "p1": {"FGM": 40, "FGA": 100, "TO": 20, "STL": 5, "DREB": 20, "OREB": 10}
            },
        },
        "teams": {
            home_team_id: {
                "name": "Home",
                "scouting": {
                    "offense": {"Fast_Break_Entries": 10, "Fast_Break_Success": 6},
                    "defense": {"HCT": {"used": 10, "success": 6}, "FCP": {"used": 10, "success": 5}},
                },
            },
            away_team_id: {
                "name": "Away",
                "scouting": {
                    "offense": {"Fast_Break_Entries": 10, "Fast_Break_Success": 3},
                    "defense": {"HCT": {"used": 10, "success": 1}, "FCP": {"used": 10, "success": 3}},
                },
            },
        },
    }

    fake_db = _FakeDB(game_doc)
    fake_ftd = _FakeFranchiseTeamDataCollection(franchise_id, home_oid, away_oid)

    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", fake_ftd)
    monkeypatch.setattr(
        franchise_routes,
        "_resolve_team_id_to_object_id",
        lambda team_id: home_oid if team_id == home_team_id else away_oid if team_id == away_team_id else None,
    )

    # Deterministic low-end values for all configured ranges.
    monkeypatch.setattr("random.randint", lambda a, b: a)
    monkeypatch.setattr("random.uniform", lambda a, b: a)

    changes = franchise_routes.update_team_attributes_after_game(
        game_id=game_id,
        franchise_id=franchise_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        winner_id=home_team_id,
        loser_id=away_team_id,
        winner_score=88,
        loser_score=80,  # score_delta = 8
    )

    home_changes = changes[home_team_id]
    away_changes = changes[away_team_id]

    # Winner paths (random.randint patched to low end `a`; snapshot from eog_inputs)
    assert home_changes["shot_threshold"] == -10
    assert home_changes["discipline"] == 0
    assert home_changes["fight"] == 0
    assert home_changes["rebound_modifier"] == 0.0
    assert home_changes["offensive_efficiency"] == -4
    assert home_changes["defensive_efficiency"] == -2
    assert home_changes["fb_efficiency"] == -2
    assert home_changes["fb_opp_modifier"] == -2
    assert home_changes["pt_efficiency"] == -3
    assert home_changes["pt_opp_modifier"] == -3
    assert home_changes["team_chemistry"] == 1

    # Loser paths
    assert away_changes["shot_threshold"] == 5
    assert away_changes["discipline"] == -3
    assert away_changes["fight"] == -3
    assert away_changes["rebound_modifier"] == pytest.approx(-0.05)
    assert away_changes["offensive_efficiency"] == -4
    assert away_changes["defensive_efficiency"] == -2
    assert away_changes["fb_efficiency"] == -2
    assert away_changes["fb_opp_modifier"] == -2
    assert away_changes["pt_efficiency"] == -3
    assert away_changes["pt_opp_modifier"] == -3
    assert away_changes["team_chemistry"] == -4

    # Both teams should have been persisted to FTD.
    assert len(fake_ftd.update_calls) == 2
