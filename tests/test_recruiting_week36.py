from bson import ObjectId

from BackEnd.api import franchise_routes


class _FakeCollection:
    def __init__(self, find_one_result=None, distinct_result=None, find_result=None):
        self.find_one_result = find_one_result
        self.distinct_result = distinct_result or []
        self.find_result = find_result or []
        self.update_calls = []

    def find_one(self, *_args, **_kwargs):
        return self.find_one_result

    def find(self, *_args, **_kwargs):
        return self.find_result

    def distinct(self, *_args, **_kwargs):
        return self.distinct_result

    def update_one(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))


class _FakePlayersDb:
    def __init__(self, count):
        self.count = count

    def count_documents(self, *_args, **_kwargs):
        return self.count


class _FakeTeamsDb:
    def __init__(self, team_docs):
        self.team_docs = team_docs

    def find(self, *_args, **_kwargs):
        return self.team_docs

    def find_one(self, *_args, **_kwargs):
        return self.team_docs[0] if self.team_docs else None


class _FakeDb:
    def __init__(self, count, team_docs):
        self.players = _FakePlayersDb(count)
        self.teams = _FakeTeamsDb(team_docs)


def test_calculate_available_roster_spots_uses_returning_non_graduates(monkeypatch):
    team_id = ObjectId()
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        _FakeCollection(find_one_result={"players": ["p1", "p2", "p3"]}),
    )
    monkeypatch.setattr(franchise_routes, "db", _FakeDb(2, []))

    spots = franchise_routes._calculate_available_roster_spots(ObjectId(), str(team_id))

    assert spots == 13


def test_week36_order_helpers_preserve_shape():
    payload = franchise_routes._normalize_week_35_recruiting_orders(
        [
            {"id": "r2", "points": 3, "scholarship": True, "playing_time": False},
            {"id": "r1", "points": 0, "scholarship": False, "playing_time": True},
        ]
    )

    assert payload == {
        "1": {"id": "r2", "points": 3, "scholarship": True, "playing_time": False},
        "2": {"id": "r1", "points": 0, "scholarship": False, "playing_time": True},
    }
    assert franchise_routes._week_35_order_entries(payload) == [
        {"id": "r2", "points": 3, "scholarship": True, "playing_time": False},
        {"id": "r1", "points": 0, "scholarship": False, "playing_time": True},
    ]

def test_save_recruiting_orders_week35_updates_separate_ftd_field(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())
    fake_ftd = _FakeCollection(find_result=[{"team_id": ObjectId(team_id)}])
    fake_frd = _FakeCollection(distinct_result=["r1", "r2"])

    monkeypatch.setattr(
        franchise_routes,
        "verify_franchise_owned_by_user",
        lambda _franchise_id, _user_id: {
            "_id": ObjectId(franchise_id),
            "week": 35,
            "user_team_id": "Morristown",
            "user_team_object_id": team_id,
            "recruiting_results": {},
        },
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", fake_ftd)
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", fake_frd)
    monkeypatch.setattr(franchise_routes, "db", _FakeDb(0, [{"_id": ObjectId(team_id), "name": "Morristown", "region": "A"}]))

    response = franchise_routes.save_recruiting_orders(
        franchise_routes.SaveRecruitingOrdersRequest(
            franchise_id=franchise_id,
            order_entries=[
                {"id": "r2", "points": 12, "scholarship": True, "playing_time": True},
                {"id": "r1", "points": 8, "scholarship": False, "playing_time": False},
            ],
        ),
        user={"user_id": "test-user-123"},
    )

    assert response["status"] == "success"
    assert fake_ftd.update_calls
    update_doc = fake_ftd.update_calls[0][0][1]["$set"]
    assert update_doc["recruiting_orders_week_35"] == {
        "1": {"id": "r2", "points": 12, "scholarship": False, "playing_time": True},
        "2": {"id": "r1", "points": 8, "scholarship": False, "playing_time": False},
    }

def test_get_recruiting_data_includes_week35_saved_orders_and_spots(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())
    monkeypatch.setattr(
        franchise_routes,
        "verify_franchise_owned_by_user",
        lambda _franchise_id, _user_id: {
            "_id": ObjectId(franchise_id),
            "week": 35,
            "user_team_id": "Morristown",
            "user_team_object_id": team_id,
            "recruiting_results": {},
        },
    )
    monkeypatch.setattr(
        franchise_routes,
        "franchise_team_data_collection",
        _FakeCollection(
            find_one_result={
                "Recruits": {"1": "legacy"},
                "recruiting_orders_week_35": {
                    "1": {"id": "r1", "points": 4, "scholarship": True, "playing_time": False}
                },
            }
        ),
    )

    class _FakeRecruitCollection:
        def find(self, *_args, **_kwargs):
            return [
                {
                    "recruit_id": "r1",
                    "name": "Recruit One",
                    "attributes": {"SC": 50, "SH": 40, "ID": 30, "OD": 20, "PS": 10, "BH": 50, "RB": 60, "AG": 70, "ST": 40, "ND": 30, "IQ": 80, "FT": 90},
                    "position_ratings": {"PG": 712},
                    "height": 76,
                    "weight": 205,
                    "archetype": "Guard",
                    "Home Region": "A",
                    "Lean": {"1": team_id, "2": None, "3": None},
                }
            ]

    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", _FakeRecruitCollection())
    monkeypatch.setattr(
        franchise_routes,
        "db",
        _FakeDb(
            2,
            [{"_id": ObjectId(team_id), "name": "Morristown", "region": "C"}],
        ),
    )
    monkeypatch.setattr(franchise_routes, "_calculate_available_roster_spots", lambda _fid, _team_id: 13)
    monkeypatch.setattr(franchise_routes, "_calculate_available_scholarships", lambda _fid, _team_id: 4)

    payload = franchise_routes.get_recruiting_data(franchise_id, user={"user_id": "test-user-123"})

    assert payload["week"] == 35
    assert payload["team_region"] == "C"
    assert payload["available_roster_spots"] == 13
    assert payload["available_scholarships"] == 4
    assert payload["saved_orders_week_35"] == {
        "1": {"id": "r1", "points": 4, "scholarship": True, "playing_time": False}
    }
    assert payload["saved_order_entries_week_35"] == [
        {"id": "r1", "points": 4, "scholarship": True, "playing_time": False}
    ]


def test_week35_team_score_applies_subtotal_then_lean_multiplier():
    # subtotal = 1 (top grid) + 10 (assigned) + 15 (PT, <=2 offers) = 26; lean #1 -> x5
    score = franchise_routes._week_35_team_score(
        "team-1",
        {"points": 10, "scholarship": False, "playing_time": True},
        {"1": "team-1", "2": "team-2", "3": None},
        scholarship_offer_count=0,
        pt_offer_count=2,
    )

    assert score == 130


def test_save_recruiting_orders_week35_rejects_points_over_budget(monkeypatch):
    franchise_id = str(ObjectId())
    team_id = str(ObjectId())

    monkeypatch.setattr(
        franchise_routes,
        "verify_franchise_owned_by_user",
        lambda _franchise_id, _user_id: {
            "_id": ObjectId(franchise_id),
            "week": 35,
            "user_team_id": "Morristown",
            "user_team_object_id": team_id,
            "recruiting_results": {},
        },
    )
    monkeypatch.setattr(franchise_routes, "franchise_team_data_collection", _FakeCollection(find_result=[{"team_id": ObjectId(team_id)}]))
    monkeypatch.setattr(franchise_routes, "franchise_recruits_data_collection", _FakeCollection(distinct_result=["r1", "r2"]))

    try:
        franchise_routes.save_recruiting_orders(
            franchise_routes.SaveRecruitingOrdersRequest(
                franchise_id=franchise_id,
                order_entries=[
                    {"id": "r1", "points": 30, "scholarship": True, "playing_time": False},
                    {"id": "r2", "points": 25, "scholarship": False, "playing_time": False},
                ],
            ),
            user={"user_id": "test-user-123"},
        )
        assert False, "Expected HTTPException for over-budget recruiting points"
    except franchise_routes.HTTPException as exc:
        assert exc.status_code == 400
        assert "50 total recruiting points" in exc.detail
