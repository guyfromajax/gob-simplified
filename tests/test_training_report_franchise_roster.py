from types import SimpleNamespace

from bson import ObjectId

from BackEnd.api import franchise_routes


def test_franchise_training_report_uses_ftd_players_for_player_list(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())
    recruit_player_id = "franchise-only-freshman"

    def _fake_ftd_find_one(_filter, projection=None):
        full_doc = {
            "players": [recruit_player_id],
            "training_reports": {
                "1": {
                    "player_logs": {},
                    "team_log": {},
                    "coaching_focus": {},
                    "training_notes": [],
                    "plays_data": {},
                    "scouting_data": {},
                    "plays_effectiveness_changes": {},
                    "defenses_effectiveness_changes": {},
                }
            },
            "team_attributes": {},
        }
        if not projection:
            return full_doc
        return {key: value for key, value in full_doc.items() if projection.get(key)}

    monkeypatch.setattr(
        franchise_routes,
        "get_user_team_from_franchise",
        lambda _doc: ("Morristown", team_id),
    )
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        SimpleNamespace(find_one=_fake_ftd_find_one),
    )
    monkeypatch.setattr(
        franchise_routes,
        "franchise_players_data_collection",
        SimpleNamespace(
            find=lambda *args, **kwargs: [
                {
                    "player_id": recruit_player_id,
                    "meta": {"first_name": "Fresh", "last_name": "Recruit"},
                    "attributes": {"SC": 10, "SH": 9, "ID": 8, "OD": 7, "PS": 6, "BH": 5, "RB": 4, "ST": 3, "AG": 2, "ND": 1, "IQ": 11, "FT": 12},
                }
            ]
        ),
    )

    class _FakeTeams:
        def find_one(self, query, projection=None):
            if query.get("_id") == ObjectId(team_id):
                return {"_id": ObjectId(team_id), "name": "Morristown", "player_ids": []}
            return None

    monkeypatch.setattr(
        franchise_routes,
        "db",
        SimpleNamespace(
            franchises=SimpleNamespace(find_one=lambda *args, **kwargs: {"_id": ObjectId(franchise_id), "schedule": [], "week": 1, "latest_training": {}}),
            teams=_FakeTeams(),
        ),
    )

    payload = franchise_routes.get_training_report(franchise_id=franchise_id, team_id=team_id, week=1)

    assert payload["status"] == "success"
    assert len(payload["players"]) == 1
    assert payload["players"][0]["id"] == recruit_player_id
    assert payload["players"][0]["name"] == "Fresh Recruit"
