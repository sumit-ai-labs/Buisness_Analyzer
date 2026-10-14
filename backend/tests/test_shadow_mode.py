import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.entity import BusinessEntity
from app.models.events import RawSearchResult
from app.services.alert_service import AlertService
from app.services.network_service import NetworkService
from app.services.research_service import ResearchService
from app.services.analysis_service import AnalysisBatchResult
from app.services.geo_matching_service import GeoMatchingService
from app.services.matcher_service import MatcherService
from app.models.events import DisruptionEvent
from app.core.config import settings


@pytest.mark.asyncio
async def test_shadow_mode_records_proposed_decisions_without_altering_production():
    net_svc = NetworkService()
    entity = BusinessEntity(
        id="ent-shadow-test",
        name="Antwerp Container Terminal",
        type="supplier",
        criticality="high",
        location="Antwerp",
        status="active",
    )
    net_svc.add_entity(entity)

    # Mock raw search and analysis
    raw = RawSearchResult(
        url="https://reuters.com/antwerp-strike",
        title="Dock strike halts Antwerp cargo",
        snippet="Active strike paralyzes all terminals in Antwerp.",
        queried_entity_id="ent-shadow-test",
        query_used="test query",
    )
    mock_event = DisruptionEvent(
        source_result_id=raw.id,
        source_url="https://reuters.com/antwerp-strike",
        headline="Dock strike halts Antwerp cargo",
        summary="Active strike paralyzes all terminals in Antwerp.",
        event_type="strike",
        location_mentioned="Antwerp",
        severity_raw="high",
        confidence=0.85,
        is_relevant=True,
    )

    geo_svc = GeoMatchingService()
    matcher_svc = MatcherService(network_service=net_svc, geo_matching_service=geo_svc)
    alert_svc = AlertService(
        network_service=net_svc,
        matcher_service=matcher_svc,
        geo_matching_service=geo_svc,
    )
    alert_svc.research_service.search_disruptions_for_network = lambda entities: [raw]
    alert_svc.analysis_service.analyze_search_results_batch = lambda results, entity_name_map=None: AnalysisBatchResult(
        events=[mock_event],
        processed_count=1,
    )

    # Enable SHADOW_MODE
    with patch.object(settings, "SHADOW_MODE", True):
        res = await alert_svc.run_monitoring_cycle()
        # In shadow mode, new_alerts_count should be 0 in production alerts dict
        assert len(alert_svc.list_alerts()) == 0
        assert res["new_alerts_count"] == 0

        # Proposed decision was captured in shadow records
        shadow_records = alert_svc.list_shadow_records()
        assert len(shadow_records) == 1
        rec = shadow_records[0]
        assert rec["headline"] == "Dock strike halts Antwerp cargo"
        assert rec["risk_level"] in ("high", "critical")
        assert rec["credibility_label"] in ("moderate", "high")
        assert "recorded_at" in rec
