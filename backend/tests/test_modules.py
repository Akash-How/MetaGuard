from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_dead_data_scan_returns_candidates() -> None:
    response = client.get("/api/dead-data/scan")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_candidates"] >= 1
    assert any(item["category"] == "orphan" for item in payload["assets"])


def test_passport_returns_trust_score() -> None:
    response = client.get("/api/passport/sandbox.sales.orders")
    assert response.status_code == 200
    payload = response.json()
    assert payload["fqn"] == "sandbox.sales.orders"
    assert payload["trust_score"]["total"] > 0


def test_storm_simulate_creates_alert() -> None:
    response = client.post(
        "/api/storm/simulate",
        json={
            "fqn": "sandbox.sales.orders",
            "changes": [
                {
                    "column": "status",
                    "change_type": "drop_column",
                    "before": "STRING",
                    "after": None,
                }
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["severity"] == "critical"
    assert payload["change_count"] == 1


def test_blast_radius_report_has_risk_score() -> None:
    response = client.get("/api/blast-radius/table/sandbox.sales.orders")
    assert response.status_code == 200
    payload = response.json()
    assert payload["overall_risk_score"] >= 0
    assert payload["entity_type"] == "table"


def test_chat_understands_module_prefix() -> None:
    response = client.post(
        "/api/chat/ask",
        json={
            "question": "In Dead Data: why is orders_archive flagged?",
            "entity_id": "sandbox.sales.orders_archive",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["module"] == "dead-data"
