"""Your-team news dispatches: same sentences the press tab used to build in the browser."""

from pathlib import Path

import pytest
from bson import ObjectId

from BackEnd.api import franchise_routes
from BackEnd.persistence.mongo import MongoStore
from BackEnd.persistence.sqlite import SqliteStore
from tests.test_persistence_adapter import _mongomock_env, _sqlite_env

TEAM = ObjectId()
FID = ObjectId()


def _doc():
    return {
        "_id": FID,
        "user_team_id": "Lancaster",
        "user_team_object_id": str(TEAM),
        "latest_training": {"week": 8},
        "season_inbox": [
            {
                "type": "training_squad_report",
                "week": 8,
                "message": "ignored",
            },
            {
                "type": "game_result",
                "week": 8,
                "result": "win",
                "user_team_name": "Lancaster",
                "opponent_team_name": "Four Corners",
                "user_score": 70,
                "opponent_score": 64,
                "copy": "Week #8: Lancaster defeated Four Corners 70-64",
                "box_score_url": "/box-score.html?game_id=g1",
            },
            {
                "type": "game_result",
                "week": 7,
                "result": "loss",
                "copy": "Week #7: Lancaster lost to Ashland 60-71",
            },
            {"type": "game_result", "week": "nope", "copy": "skip"},
        ],
        "season_news": [
            {"story_id": "w8-upset-report", "week": 8, "type": "upset_report", "headline": "Week 8 Upset Report"},
        ],
    }


def test_dispatch_wording_matches_the_old_press_tab():
    items = franchise_routes._news_dispatch_items(_doc())
    assert [item["headline"] for item in items] == [
        "Week 8 training report",
        "Week 8 Practice Squad development report",
        "Lancaster defeated Four Corners 70-64",
        "Week #7: Lancaster lost to Ashland 60-71",
    ]
    assert items[0]["target"].startswith("/training-report.html?")
    assert "from=news" in items[0]["target"]
    assert "week=8" in items[0]["target"]
    assert items[0]["link_label"] == "view"
    assert items[1]["target"].startswith("/training-squad-report.html?")
    assert items[2]["target"] == "/box-score.html?game_id=g1"
    assert items[2]["link_label"] == "box score"
    assert all(item["yours"] is True for item in items)
    assert [item["type"] for item in items] == [
        "training_report",
        "training_squad_report",
        "game_result",
        "game_result",
    ]


def test_a_loss_with_names_uses_lost_to():
    doc = _doc()
    doc["latest_training"] = {}
    doc["season_inbox"] = [{
        "type": "game_result",
        "week": 4,
        "result": "loss",
        "user_team_name": "Lancaster",
        "opponent_team_name": "Ashland",
        "user_score": 60,
        "opponent_score": 71,
        "copy": "Week #4: Lancaster lost to Ashland 60-71",
        "box_score_url": "/box-score.html?game_id=g2",
    }]
    items = franchise_routes._news_dispatch_items(doc)
    assert items[0]["headline"] == "Lancaster lost to Ashland 60-71"


def _store(tmp_path: Path, kind: str):
    if kind == "sqlite":
        return SqliteStore(_sqlite_env(tmp_path))
    return MongoStore(_mongomock_env(tmp_path))


@pytest.mark.parametrize("kind", ["mongo", "sqlite"])
def test_news_route_returns_dispatches_from_the_stored_doc(tmp_path, kind, monkeypatch):
    store = _store(tmp_path, kind)
    store.db.franchises.insert_one(_doc())
    monkeypatch.setattr(franchise_routes, "db", store.db)

    def _owned(franchise_id, _user_id):
        return store.db.franchises.find_one({"_id": FID})

    monkeypatch.setattr(franchise_routes, "verify_franchise_owned_by_user", _owned)
    body = franchise_routes.get_franchise_news(str(FID), category=None, user={"user_id": "u"})
    assert body["news"][0]["headline"] == "Week 8 Upset Report"
    assert body["dispatches"][0]["headline"] == "Week 8 training report"
    assert body["dispatches"][2]["yours"] is True
    assert body["dispatches"][2]["week"] == 8
