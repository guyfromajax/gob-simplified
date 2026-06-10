from bson import ObjectId

from BackEnd.api import franchise_routes


class _FakeCollection:
    def __init__(self, find_one_result=None, distinct_result=None):
        self.find_one_result = find_one_result
        self.distinct_result = distinct_result or []
        self.update_calls = []

    def find_one(self, *_args, **_kwargs):
        return self.find_one_result

    def distinct(self, *_args, **_kwargs):
        return self.distinct_result

    def update_one(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))


class _UnusedDb:
    pass


class _TrainingFranchisesCollection:
    def __init__(self, franchise_doc):
        self.franchise_doc = franchise_doc

    def find_one(self, *_args, **_kwargs):
        return self.franchise_doc


class _TrainingDb:
    def __init__(self, franchise_doc):
        self.franchises = _TrainingFranchisesCollection(franchise_doc)


def test_team_was_newly_added_to_lean_detects_additions_not_rank_moves():
    team_id = "team-a"
    prior = {"1": "team-b", "2": None, "3": None}
    added = {"1": "team-b", "2": team_id, "3": None}
    moved_up = {"1": team_id, "2": "team-b", "3": None}
    assert franchise_routes._team_was_newly_added_to_lean(prior, added, team_id) is True
    assert franchise_routes._team_was_newly_added_to_lean(prior, moved_up, team_id) is False


def test_fcc_current_week_invite_recruit_skips_outside_window_and_processed_weeks(monkeypatch):
    team_id = str(ObjectId())
    franchise_doc = {"_id": ObjectId(), "week": 19, "recruiting_results": {}}
    assert franchise_routes._fcc_current_week_invite_recruit(
        franchise_doc, team_id, {"1": "r1"}
    ) is None

    franchise_doc["week"] = 27
    assert franchise_routes._fcc_current_week_invite_recruit(
        franchise_doc, team_id, {"1": "r1"}
    ) is None

    franchise_doc["week"] = 22
    franchise_doc["recruiting_results"] = {"22": {team_id: "r1"}}

    def _missing_recruit(_query, projection=None):
        return None

    monkeypatch.setattr(
        franchise_routes.franchise_recruits_data_collection,
        "find_one",
        _missing_recruit,
    )
    assert franchise_routes._fcc_current_week_invite_recruit(
        franchise_doc, team_id, {"1": "r1", "2": "r2"}
    ) is None


def test_fcc_current_week_invite_recruit_returns_assigned_visit_after_processing(monkeypatch):
    team_id = str(ObjectId())
    franchise_id = ObjectId()
    franchise_doc = {
        "_id": franchise_id,
        "week": 22,
        "recruiting_results": {"22": {team_id: "r1"}},
    }

    monkeypatch.setattr(
        franchise_routes.franchise_recruits_data_collection,
        "find_one",
        lambda query, projection=None: {
            "recruit_id": "r1",
            "name": "Assigned Recruit",
            "archetype": "Shooter",
            "height": 75,
            "weight": 195,
            "position_ratings": {"SG": 52},
        },
    )

    payload = franchise_routes._fcc_current_week_invite_recruit(
        franchise_doc, team_id, {"1": "r2", "2": "r3"}
    )
    assert payload == {
        "recruit_id": "r1",
        "name": "Assigned Recruit",
        "archetype": "Shooter",
        "height": "6'3\"",
        "weight": 195,
        "rt": 52,
        "status": "assigned",
    }


def test_fcc_current_week_invite_recruit_skips_pending_after_processed_no_visit(monkeypatch):
    team_id = str(ObjectId())
    franchise_doc = {
        "_id": ObjectId(),
        "week": 22,
        "recruiting_results": {"22": {}},
    }
    assert franchise_routes._fcc_current_week_invite_recruit(
        franchise_doc, team_id, {"1": "r2", "2": "r3"}
    ) is None


def test_fcc_current_week_invite_recruit_returns_top_remaining_order(monkeypatch):
    team_id = str(ObjectId())
    franchise_id = ObjectId()
    franchise_doc = {
        "_id": franchise_id,
        "week": 22,
        "recruiting_results": {"20": {team_id: "r1"}, "21": {team_id: "r2"}},
    }
    saved_orders = {"1": "r1", "2": "r2", "3": "r3"}

    monkeypatch.setattr(
        franchise_routes.franchise_recruits_data_collection,
        "find_one",
        lambda query, projection=None: {
            "recruit_id": "r3",
            "name": "Test Recruit",
            "archetype": "Slasher",
            "height": 77,
            "weight": 210,
            "position_ratings": {"SG": 44},
        },
    )

    payload = franchise_routes._fcc_current_week_invite_recruit(
        franchise_doc, team_id, saved_orders
    )
    assert payload == {
        "recruit_id": "r3",
        "name": "Test Recruit",
        "archetype": "Slasher",
        "height": "6'5\"",
        "weight": 210,
        "rt": 44,
        "status": "pending",
    }


def test_save_recruiting_orders_week20_only_persists_orders(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())
    fake_ftd = _FakeCollection()
    fake_frd = _FakeCollection(distinct_result=["r1", "r2"])

    monkeypatch.setattr(
        franchise_routes,
        "verify_franchise_owned_by_user",
        lambda _franchise_id, _user_id: {
            "_id": ObjectId(franchise_id),
            "week": 20,
            "user_team_id": "Morristown",
            "user_team_object_id": team_id,
            "recruiting_results": {},
        },
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", fake_ftd)
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", fake_frd)
    monkeypatch.setattr(franchise_routes, "db", _UnusedDb())

    response = franchise_routes.save_recruiting_orders(
        franchise_routes.SaveRecruitingOrdersRequest(
            franchise_id=franchise_id,
            recruit_ids=["r2", "r1"],
        ),
        user={"user_id": "test-user-123"},
    )

    assert response == {
        "status": "success",
        "saved_orders": {"1": "r2", "2": "r1"},
        "results_week": None,
    }
    assert len(fake_ftd.update_calls) == 1
    update_doc = fake_ftd.update_calls[0][0][1]["$set"]
    assert update_doc["Recruits"] == {"1": "r2", "2": "r1"}


def test_save_recruiting_orders_week20_rejects_late_save_after_results(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())
    fake_ftd = _FakeCollection()
    fake_frd = _FakeCollection(distinct_result=["r1"])

    monkeypatch.setattr(
        franchise_routes,
        "verify_franchise_owned_by_user",
        lambda _franchise_id, _user_id: {
            "_id": ObjectId(franchise_id),
            "week": 20,
            "user_team_id": "Morristown",
            "user_team_object_id": team_id,
            "recruiting_results": {"20": {"status": "processed"}},
        },
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", fake_ftd)
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", fake_frd)
    monkeypatch.setattr(franchise_routes, "db", _UnusedDb())

    try:
        franchise_routes.save_recruiting_orders(
            franchise_routes.SaveRecruitingOrdersRequest(
                franchise_id=franchise_id,
                recruit_ids=["r1"],
            ),
            user={"user_id": "test-user-123"},
        )
        assert False, "Expected late recruiting save to be rejected after weekly results exist"
    except franchise_routes.HTTPException as exc:
        assert exc.status_code == 400
        assert "already been processed" in exc.detail
    assert fake_ftd.update_calls == []


def test_run_training_week20_requires_saved_recruiting_orders(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())
    franchise_doc = {
        "_id": ObjectId(franchise_id),
        "week": 20,
        "results": {},
        "recruiting_results": {},
        "training_status": {"training_completed": False, "session_type": "in-season"},
        "user_team_id": "Morristown",
        "user_team_object_id": team_id,
    }

    monkeypatch.setattr(franchise_routes, "db", _TrainingDb(franchise_doc))
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        _FakeCollection(find_one_result={"Recruits": {}}),
    )

    try:
        franchise_routes._run_franchise_training_impl(
            franchise_routes.FranchiseTrainingRequest(
                franchise_id=franchise_id,
                training_data={"player_drills": {}, "team_drills": {}, "general": {}},
            )
        )
        assert False, "Expected HTTPException when week 20 training runs without saved recruiting orders"
    except franchise_routes.HTTPException as exc:
        assert exc.status_code == 400
        assert "save recruiting orders before running training in week 20" in exc.detail
