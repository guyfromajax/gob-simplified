from fastapi.testclient import TestClient

from BackEnd.api.api import app
from BackEnd.api import feedback_routes

client = TestClient(app)


class _FakeFeedbackCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        self.docs.append(doc)
        return type("Result", (), {"inserted_id": "fake-id"})()


def test_feedback_submit_success(monkeypatch):
    fake_collection = _FakeFeedbackCollection()
    monkeypatch.setattr(feedback_routes, "feedback_collection", fake_collection)
    monkeypatch.setattr(feedback_routes, "_last_feedback_by_ip", {})
    monkeypatch.setattr(feedback_routes, "send_feedback_email", lambda **kwargs: True)

    response = client.post(
        "/api/feedback",
        json={
            "category": "bug",
            "message": "Playbook percentages looked wrong on initial load.",
            "reporter_email": "coach@example.com",
            "page_url": "https://gob-test.netlify.app/playbooks.html",
            "page_path": "/playbooks.html",
            "mode": "franchise",
            "user_label": "Coach Jamie",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["email_sent"] is True
    assert len(fake_collection.docs) == 1
    assert fake_collection.docs[0]["category"] == "bug"


def test_feedback_submit_rate_limited(monkeypatch):
    fake_collection = _FakeFeedbackCollection()
    monkeypatch.setattr(feedback_routes, "feedback_collection", fake_collection)
    monkeypatch.setattr(feedback_routes, "_last_feedback_by_ip", {})
    monkeypatch.setattr(feedback_routes, "send_feedback_email", lambda **kwargs: True)

    payload = {"category": "general", "message": "First message with enough detail."}

    first = client.post("/api/feedback", json=payload)
    assert first.status_code == 200

    second = client.post("/api/feedback", json=payload)
    assert second.status_code == 429
