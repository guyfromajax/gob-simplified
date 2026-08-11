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
        {"week": 1, "training_status": {"week": 1, "training_completed": True}},
        object(),
        team_id,
    )

    assert inactive == {"roster_count": 0, "cut_count": 0, "cut_required": False}
    assert active == {"roster_count": 15, "cut_count": 3, "cut_required": True}


def test_maybe_initialize_practice_squad_week_1_defers_when_user_cut_pending(monkeypatch):
    franchise_id = object()
    team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    franchise_doc = {
        "week": 1,
        "training_status": {
            "week": 1,
            "cpu_training_camp_cuts_applied": True,
            "training_completed": True,
        },
        "practice_squad": {},
    }

    class _FakeCollection:
        def find_one(self, *_args, **_kwargs):
            return {"players": ["p1"] * 15}

    called = {"init": False}

    def _fake_init(*_args, **_kwargs):
        called["init"] = True
        return {"initialized": True}

    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _FakeCollection())
    monkeypatch.setattr(
        "BackEnd.practice_squad.manager.initialize_practice_squad",
        _fake_init,
    )

    result = franchise_routes._maybe_initialize_practice_squad_week_1(
        franchise_id,
        franchise_doc,
        user_team_object_id=team_id,
        defer_if_user_cut_pending=True,
    )

    assert result is None
    assert called["init"] is False


def test_maybe_initialize_practice_squad_week_1_runs_after_user_cut(monkeypatch):
    franchise_id = object()
    team_id = "aaaaaaaaaaaaaaaaaaaaaaaa"
    franchise_doc = {
        "week": 1,
        "training_status": {
            "week": 1,
            "cpu_training_camp_cuts_applied": True,
            "training_completed": True,
        },
        "practice_squad": {},
        "season_news": [],
    }

    class _FakeCollection:
        def find_one(self, *_args, **_kwargs):
            return {"players": ["p1"] * 12}

        def update_one(self, *_args, **_kwargs):
            return None

    ps_state = {"initialized": True, "teams": {}}

    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _FakeCollection())
    monkeypatch.setattr(
        franchise_routes.db.franchises,
        "update_one",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        "BackEnd.practice_squad.manager.initialize_practice_squad",
        lambda *_a, **_k: ps_state,
    )
    monkeypatch.setattr(
        "BackEnd.practice_squad.manager.build_roster_announcement_story",
        lambda *_a, **_k: {"story_id": "ps_rosters", "headline": "PS Rosters"},
    )

    result = franchise_routes._maybe_initialize_practice_squad_week_1(
        franchise_id,
        franchise_doc,
        user_team_object_id=team_id,
        defer_if_user_cut_pending=False,
    )

    assert result == ps_state
    assert franchise_doc["practice_squad"] == ps_state
