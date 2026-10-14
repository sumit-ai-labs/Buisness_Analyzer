import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.models.entity import BusinessEntity, BusinessRelationship
from app.services.network_service import get_network_service
from app.services.alert_service import get_alert_service


def test_health_check_endpoint():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_end_to_end_monitoring_flow():
    client = TestClient(app)
    net_service = get_network_service()

    # Create supplier and dependent factory
    supplier = net_service.add_entity(
        BusinessEntity(
            id="e2e-supp-1",
            name="Rotterdam Logistics Port",
            type="route",
            location="Rotterdam, Netherlands",
            criticality="high",
        )
    )
    factory = net_service.add_entity(
        BusinessEntity(
            id="e2e-fact-1",
            name="Amsterdam Distribution Hub",
            type="warehouse",
            location="Amsterdam, Netherlands",
            criticality="high",
        )
    )
    net_service.add_relationship(
        BusinessRelationship(
            source_id="e2e-fact-1",
            target_id="e2e-supp-1",
            relationship_type="depends_on",
            dependency_weight=0.9,
        )
    )

    # Trigger monitoring run
    response = client.post("/api/monitor/run")
    assert response.status_code == 200
    result = response.json()
    assert "raw_results_count" in result
    assert "new_alerts_count" in result

    # Check dashboard stats
    stats_resp = client.get("/api/dashboard/stats")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_alerts" in stats

    # Fetch alerts
    alerts_resp = client.get("/api/alerts")
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()

    if alerts:
        alert_id = alerts[0]["id"]
        explain_resp = client.get(f"/api/alerts/{alert_id}/explain")
        assert explain_resp.status_code == 200
        explanation = explain_resp.json()
        assert "risk_assessment" in explanation


@pytest.mark.asyncio
async def test_concurrency_lock_409_conflict():
    alert_service = get_alert_service()
    
    # Manually acquire lock to simulate ongoing cycle
    async with alert_service._lock:
        client = TestClient(app)
        response = client.post("/api/monitor/run")
        assert response.status_code == 409
        assert "in progress" in response.json()["detail"]
