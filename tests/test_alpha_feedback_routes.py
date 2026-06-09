from fastapi.testclient import TestClient

from BackEnd.api import alpha_feedback_routes
from BackEnd.api.api import app


client = TestClient(app)


class _FakeCollection:
    def __init__(self):
        self.updates = []

    def update_one(self, query, update, **kwargs):
        self.updates.append((query, update, kwargs))
        return type("Result", (), {})()


def _payload(**overrides):
    payload = {
        "ratings": {
            "live_gameplay": "Good",
            "between_games": "Good",
            "training": "Good",
            "franchise_mode": "Good",
            "high_school_setting": "Good",
            "onboarding": "Good",
            "game_length": "Just Right",
            "learning_curve": "Just Right",
        },
        "optional_notes": {},
        "favorite": "The strategy.",
        "least_favorite": "The loading time.",
        "would_recommend": True,
    }
    payload.update(overrides)
    return payload


def _prepare(monkeypatch):
    feedback_collection = _FakeCollection()
    users_collection = _FakeCollection()
    sent_emails = []
    monkeypatch.setattr(alpha_feedback_routes, "alpha_feedback_collection", feedback_collection)
    monkeypatch.setattr(alpha_feedback_routes, "users_collection", users_collection)
    monkeypatch.setattr(alpha_feedback_routes, "_last_submit_by_ip", {})
    monkeypatch.setattr(
        alpha_feedback_routes,
        "send_alpha_feedback_email",
        lambda **kwargs: sent_emails.append(kwargs) or True,
    )
    return feedback_collection, sent_emails


def test_alpha_feedback_allows_blank_anything_else(monkeypatch):
    feedback_collection, sent_emails = _prepare(monkeypatch)

    response = client.post("/api/alpha-feedback", json=_payload())

    assert response.status_code == 200
    stored = feedback_collection.updates[0][1]["$set"]
    assert stored["anything_else"] == ""
    assert sent_emails[0]["anything_else"] == ""


def test_alpha_feedback_stores_anything_else(monkeypatch):
    feedback_collection, sent_emails = _prepare(monkeypatch)

    response = client.post(
        "/api/alpha-feedback",
        json=_payload(anything_else="  Keep improving the tutorials.  "),
    )

    assert response.status_code == 200
    stored = feedback_collection.updates[0][1]["$set"]
    assert stored["anything_else"] == "Keep improving the tutorials."
    assert sent_emails[0]["anything_else"] == "Keep improving the tutorials."
