from types import SimpleNamespace

from bson import ObjectId

from BackEnd.api import franchise_routes


def test_standings_region_filter(monkeypatch):
    franchise_id = ObjectId()
    team_a = ObjectId()
    team_b = ObjectId()

    fake_db = SimpleNamespace(
        franchises=SimpleNamespace(
            find_one=lambda *args, **kwargs: {
                "_id": franchise_id,
                "schedule": [],
                "week": 1,
                "results": {},
            }
        ),
        teams=SimpleNamespace(
            find=lambda *args, **kwargs: [
                {"_id": team_a, "name": "A", "region": "A", "conference": 1},
                {"_id": team_b, "name": "B", "region": "B", "conference": 3},
            ]
        ),
    )
    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(franchise_routes, "_ftd_team_list_for_franchise", lambda fid: {str(team_a): "A", str(team_b): "B"})
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        SimpleNamespace(find=lambda *args, **kwargs: []),
    )
    monkeypatch.setitem(__import__("sys").modules, "BackEnd.utils.franchise_standings", SimpleNamespace(
        calculate_franchise_standings=lambda results, team_list: {
            str(team_a): {"W": 1, "L": 0, "PF": 50, "PA": 40},
            str(team_b): {"W": 0, "L": 1, "PF": 40, "PA": 50},
        }
    ))

    payload = franchise_routes.standings(str(franchise_id), region="A")
    assert len(payload["standings"]) == 1
    assert payload["standings"][0]["region"] == "A"


def test_team_stats_scope_filters_to_user_conference(monkeypatch):
    franchise_id = ObjectId()
    user_team = ObjectId()
    team_same_conf = ObjectId()
    team_other_conf = ObjectId()

    fake_db = SimpleNamespace(
        franchises=SimpleNamespace(
            find_one=lambda *args, **kwargs: {
                "_id": franchise_id,
                "results": {},
                "user_team_id": "User",
                "user_team_object_id": str(user_team),
            }
        ),
        teams=SimpleNamespace(
            find_one=lambda query, projection=None: {
                str(user_team): {"conference": 1, "region": "A"},
                str(team_same_conf): {"conference": 1, "region": "A"},
                str(team_other_conf): {"conference": 2, "region": "A"},
            }.get(str(query["_id"]), {"conference": None, "region": ""}),
            find=lambda *args, **kwargs: [
                {"_id": user_team, "conference": 1, "region": "A", "mascot": "M"},
                {"_id": team_same_conf, "conference": 1, "region": "A", "mascot": "M"},
            ],
        ),
    )
    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(franchise_routes, "_ftd_team_list_for_franchise", lambda fid: {
        str(user_team): "User",
        str(team_same_conf): "Same",
        str(team_other_conf): "Other",
    })
    monkeypatch.setattr(
        franchise_routes,
        "franchise_players_data_collection",
        SimpleNamespace(find=lambda *args, **kwargs: []),
    )
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        SimpleNamespace(find=lambda *args, **kwargs: []),
    )
    monkeypatch.setattr(
        franchise_routes,
        "aggregate_team_stats_from_players",
        lambda players, team_ids, **kwargs: [{"team_id": tid, "team": name, "stats": {}} for tid, name in team_ids.items()],
    )

    payload = franchise_routes.team_stats(str(franchise_id), scope="conference")
    returned_ids = {team["team_id"] for team in payload["teams"]}
    assert returned_ids == {str(user_team), str(team_same_conf)}


def test_team_traits_scope_filters_to_user_region(monkeypatch):
    franchise_id = ObjectId()
    user_team = ObjectId()
    team_same_region = ObjectId()
    team_other_region = ObjectId()

    fake_db = SimpleNamespace(
        franchises=SimpleNamespace(
            find_one=lambda *args, **kwargs: {
                "_id": franchise_id,
                "user_team_id": "User",
                "user_team_object_id": str(user_team),
            }
        ),
        teams=SimpleNamespace(
            find_one=lambda query, projection=None: {
                str(user_team): {"conference": 1, "region": "A", "name": "User", "primary_color": "#000"},
                str(team_same_region): {"conference": 2, "region": "A", "name": "Same", "primary_color": "#000"},
                str(team_other_region): {"conference": 3, "region": "B", "name": "Other", "primary_color": "#000"},
            }.get(str(query["_id"]), None),
        ),
    )
    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(franchise_routes, "_ftd_team_list_for_franchise", lambda fid: {
        str(user_team): "User",
        str(team_same_region): "Same",
        str(team_other_region): "Other",
    })
    monkeypatch.setattr(
        franchise_routes,
        "franchise_players_data_collection",
        SimpleNamespace(find=lambda *args, **kwargs: []),
    )

    payload = franchise_routes.team_traits(str(franchise_id), scope="region")
    returned_ids = {team["team_id"] for team in payload["teams"]}
    assert returned_ids == {str(user_team), str(team_same_region)}


def test_leaders_view_scope_filters_to_user_conference(monkeypatch):
    franchise_id = ObjectId()
    user_team = ObjectId()
    other_team = ObjectId()
    base_player = {
        "player_id": "p1",
        "first_name": "A",
        "last_name": "One",
        "value": 10,
    }

    fake_db = SimpleNamespace(
        franchises=SimpleNamespace(
            find_one=lambda *args, **kwargs: {
                "_id": franchise_id,
                "user_team_id": "User",
                "user_team_object_id": str(user_team),
            }
        ),
        teams=SimpleNamespace(
            find_one=lambda query, projection=None: {"conference": 1, "region": "A"} if str(query["_id"]) == str(user_team) else None,
            find=lambda query, projection=None: [
                {"_id": user_team, "name": "User Team"},
            ],
        ),
    )
    monkeypatch.setattr(franchise_routes, "db", fake_db)
    monkeypatch.setattr(
        franchise_routes,
        "get_leaders",
        lambda franchise_id, scope, stat, limit: [
            {**base_player, "team": "User Team"},
            {**base_player, "player_id": "p2", "team": "Other Team"},
        ],
    )

    payload = franchise_routes.leaders(str(franchise_id), view_scope="conference")
    assert all(entry["team"] == "User Team" for entry in payload["PTS"])
