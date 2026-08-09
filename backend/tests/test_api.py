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
