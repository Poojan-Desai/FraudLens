import pytest

from fastapi.testclient import TestClient

from backend.app.main import app


def test_health_and_attack_endpoints():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        detected = client.get("/api/v1/attacks/takeover?threshold=0.80")
        assert detected.status_code == 200
        assert detected.json()["detected"] is True
        missed = client.get("/api/v1/attacks/travel?threshold=0.90")
        assert missed.json()["detected"] is False


def test_strategy_endpoint_rejects_invalid_probability():
    with TestClient(app) as client:
        response = client.post("/api/v1/strategy/simulate", json={
            "threshold": 0.42,
            "transactions": [{"transaction_id": 1, "amount": 10, "fraud_probability": 1.2, "is_fraud": False}],
        })
        assert response.status_code == 422


@pytest.mark.parametrize("transactions,assumptions", [
    ([{"transaction_id": i, "amount": 1e308, "fraud_probability": .1, "is_fraud": True} for i in (1, 2)], {}),
    ([{"transaction_id": i, "amount": 1e308, "fraud_probability": .9, "is_fraud": True} for i in (1, 2)], {}),
    ([{"transaction_id": i, "amount": 1, "fraud_probability": .9, "is_fraud": False} for i in (1, 2)], {"false_positive_cost": 1e308}),
    ([{"transaction_id": i, "amount": 1, "fraud_probability": .9, "is_fraud": True} for i in (1, 2)], {"manual_review_cost": 1e308}),
])
def test_strategy_endpoint_rejects_aggregate_overflow_without_server_error(transactions, assumptions):
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/strategy/simulate", json={"transactions": transactions, "assumptions": assumptions})
    assert response.status_code == 422
    assert response.json() == {"detail": "Strategy aggregates exceed the supported finite numeric range"}


def test_strategy_endpoint_preserves_normal_cost_results():
    with TestClient(app) as client:
        response = client.post("/api/v1/strategy/simulate", json={
            "transactions": [{"transaction_id": 1, "amount": 100, "fraud_probability": .1, "is_fraud": True}],
        })
    assert response.status_code == 200
    assert response.json()["missed_fraud_loss"] == 65
    assert response.json()["total_strategy_cost"] == 65
