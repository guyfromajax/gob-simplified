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
