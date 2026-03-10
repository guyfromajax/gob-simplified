from BackEnd.api import franchise_routes


def test_choose_cut_player_ids_prefers_lowest_rt_then_oldest(monkeypatch):
    monkeypatch.setattr(franchise_routes.random, "random", lambda: 0.5)

    roster = ["p1", "p2", "p3", "p4"]
    fpd_map = {
        "p1": {"position_ratings": {"PG": 60}, "meta": {"year": "Freshman"}},
        "p2": {"position_ratings": {"PG": 40}, "meta": {"year": "Freshman"}},
        "p3": {"position_ratings": {"PG": 40}, "meta": {"year": "Senior"}},
        "p4": {"position_ratings": {"PG": 55}, "meta": {"year": "Junior"}},
    }

    cut_ids = franchise_routes._choose_cut_player_ids(roster, fpd_map, 2)

    assert cut_ids == ["p3", "p2"]


def test_week_1_cut_requirement_only_applies_after_training_completed(monkeypatch):
    team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"

    class _FakeCollection:
        def find_one(self, *_args, **_kwargs):
            return {"players": ["p1"] * 15}

    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _FakeCollection())

    inactive = franchise_routes._week_1_cut_requirement(
        {"week": 1, "training_status": {"training_completed": False}},
        object(),
        team_id,
    )
    active = franchise_routes._week_1_cut_requirement(
        {"week": 1, "training_status": {"training_completed": True}},
        object(),
        team_id,
    )

    assert inactive == {"roster_count": 0, "cut_count": 0, "cut_required": False}
    assert active == {"roster_count": 15, "cut_count": 3, "cut_required": True}
