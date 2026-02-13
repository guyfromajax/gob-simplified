from BackEnd.api import api


class DummyCollection:
    def __init__(self, doc):
        self.doc = doc
        self.last_update = None

    def find_one(self, query, *_args, **_kwargs):
        if query.get("_id") == self.doc.get("_id"):
            return dict(self.doc)
        return None

    def update_one(self, query, update, *_args, **_kwargs):
        if query.get("_id") == self.doc.get("_id"):
            self.last_update = update
            set_data = update.get("$set", {})
            self.doc.update(set_data)


def test_restore_timeout_resume_state_infers_next_play_type_when_missing():
    collection = DummyCollection(
        {
            "_id": "game-1",
            "quarter": 2,
            "timeout_offense_team_id": "HOME_TEAM_ID",
        }
    )
    request = api.QuarterSimulationRequest(home_team="Home", away_team="Away", mode="single")

    saved = api.restore_timeout_resume_state("game-1", request, collection)

    assert saved is not None
    assert saved["timeout_next_play_type"] == "SIDE_INBOUND"
    assert collection.last_update == {"$set": {"timeout_next_play_type": "SIDE_INBOUND"}}


def test_restore_timeout_resume_state_returns_none_when_timeout_markers_missing():
    collection = DummyCollection({"_id": "game-2", "quarter": 2})
    request = api.QuarterSimulationRequest(home_team="Home", away_team="Away", mode="single")

    saved = api.restore_timeout_resume_state("game-2", request, collection)

    assert saved is None
    assert collection.last_update is None
