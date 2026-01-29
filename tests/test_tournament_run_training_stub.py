"""Training is disabled in Tournament mode. POST /tournament/run-training returns 404."""
from fastapi.testclient import TestClient

from BackEnd.api.api import app

client = TestClient(app)


def test_run_training_returns_404():
    res = client.post(
        "/tournament/run-training",
        json={"tournament_id": "000000000000000000000001", "training_data": {}},
    )
    assert res.status_code == 404
    data = res.json()
    assert "detail" in data
    assert "Training" in data["detail"] and "not available" in data["detail"]
