from datetime import datetime, timezone

import pytest
from unittest.mock import MagicMock

from app.models.credibility import CredibilityAssessment
from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent, RawSearchResult
from app.models.geo import EventLocation, GeoVerificationResult
from app.models.risk import Alert, RiskAssessment
from app.services.alert_service import AlertService
from app.services.analysis_service import AnalysisBatchResult
from app.services.matcher_service import MatcherService
from app.services.network_service import NetworkService


def _event(event_id="event-1") -> DisruptionEvent:
    return DisruptionEvent(
        id=event_id,
        source_url="https://example.com/report",
        source_result_id="raw-1",
        headline="Strike disrupts port operations",
        summary="Port operations are delayed by an active strike.",
        event_type="strike",
        location_mentioned="Mumbai",
        severity_raw="high",
        extracted_entities=["Mumbai Port"],
        confidence=0.82,
        is_relevant=True,
    )


def _credibility(event_id="event-1", gated=False) -> CredibilityAssessment:
    return CredibilityAssessment(
        event_id=event_id,
        source_domain="example.com",
        source_reputation_score=0.5,
        source_tier="unverified",
        corroborating_source_count=0,
        corroboration_score=0.0,
        content_style_score=0.5,
        model_version="test",
        llm_extraction_confidence=0.82,
        authenticity_score=32.0 if gated else 62.0,
        confidence_label="unconfirmed" if gated else "moderate",
        is_gated=gated,
        factors={
            "source_reputation": 17.5,
            "corroboration": 0.0,
            "content_style": 10.0,
            "llm_extraction_confidence": 16.4,
        },
    )


def test_unconfirmed_event_summary_contract_is_not_full_event():
    service = AlertService()
    event = _event()
    credibility = _credibility(gated=True)
    event.credibility_assessment_id = credibility.id
    service._unconfirmed_events[event.id] = event
    service._credibility_assessments[credibility.id] = credibility

    payload = service.list_unconfirmed_events()

    assert len(payload) == 1
    item = payload[0]
    assert item["event_id"] == event.id
    assert item["headline"] == event.headline
    assert item["authenticity_score"] == 32.0
    assert item["confidence_label"] == "unconfirmed"
    assert item["is_gated"] is True
    assert "source_result_id" not in item
    assert "summary" not in item


def test_alert_explain_contract_contains_actual_backend_fields():
    service = AlertService()
    event = _event()
    credibility = _credibility()
    geo = GeoVerificationResult(
        event_id=event.id,
        event_location=EventLocation(
            raw_text="Mumbai",
            city="Mumbai",
            latitude=19.076,
            longitude=72.8777,
            confidence=0.9,
            source="test",
            is_resolved=True,
        ),
        status="LOCATION_VERIFIED",
        location_confidence=90.0,
        entity_match_confidence=85.0,
        primary_matched_entity_id="entity-1",
        primary_matched_entity_name="Mumbai Port",
    )
    assessment = RiskAssessment(
        event_id=event.id,
        entity_id="entity-1",
        severity_score=72.0,
        factors={"dependency_weight_pct": 100.0},
        risk_level="high",
    )
    alert = Alert(
        event_id=event.id,
        risk_assessment_id=assessment.id,
        entity_ids=["entity-1"],
        message="Test alert",
        dedupe_key="dedupe",
    )
    entity = BusinessEntity(
        id="entity-1",
        name="Mumbai Port",
        type="route",
        location="Mumbai, India",
        criticality="high",
    )
    service.network_service.add_entity(entity)
    event.credibility_assessment_id = credibility.id
    event.geo_verification_id = geo.id
    service._events[event.id] = event
    service._credibility_assessments[credibility.id] = credibility
    service._geo_verifications[geo.id] = geo
    service._event_geo_map[event.id] = geo.id
    service._assessments[assessment.id] = assessment
    service._alerts[alert.id] = alert

    payload = service.explain_alert(alert.id)

    assert set(payload.keys()) == {
        "alert",
        "event",
        "risk_assessment",
        "credibility_assessment",
        "geo_verification",
        "weather_signal",
        "impacted_entities",
        "last_monitored_at",
    }
    assert payload["alert"]["id"] == alert.id
    assert payload["risk_assessment"]["risk_level"] == "high"
    assert payload["geo_verification"]["status"] == "LOCATION_VERIFIED"


def test_matcher_reuses_provided_geo_result_without_recomputing():
    network = NetworkService()
    network.add_entity(
        BusinessEntity(
            id="entity-1",
            name="Mumbai Port",
            type="route",
            location="Mumbai, India",
            criticality="high",
        )
    )
    geo_service = MagicMock()
    matcher = MatcherService(network_service=network, geo_matching_service=geo_service)
    event = _event()
    geo = GeoVerificationResult(
        event_id=event.id,
        event_location=EventLocation(raw_text="Mumbai"),
        status="LOCATION_VERIFIED",
        location_confidence=90.0,
        entity_match_confidence=88.0,
        primary_matched_entity_id="entity-1",
        primary_matched_entity_name="Mumbai Port",
    )

    impact = matcher.match_event_to_network(event, geo_result=geo)

    assert impact is not None
    assert impact.matched_entity_ids == ["entity-1"]
    geo_service.verify_and_match.assert_not_called()


@pytest.mark.asyncio
async def test_alert_service_passes_geo_result_to_matcher():
    event = _event()
    raw = RawSearchResult(
        id="raw-1",
        url=event.source_url,
        title=event.headline,
        snippet=event.summary,
        queried_entity_id="entity-1",
        query_used="test",
    )
    entity = BusinessEntity(
        id="entity-1",
        name="Mumbai Port",
        type="route",
        location="Mumbai, India",
        criticality="high",
    )
    geo = GeoVerificationResult(
        event_id=event.id,
        event_location=EventLocation(raw_text="Mumbai"),
        status="LOCATION_VERIFIED",
        location_confidence=90.0,
        entity_match_confidence=88.0,
        primary_matched_entity_id="entity-1",
        primary_matched_entity_name="Mumbai Port",
    )

    network = MagicMock()
    network.list_entities.return_value = [entity]
    network.get_entity.return_value = entity
    research = MagicMock()
    research.search_disruptions_for_network.return_value = [raw]
    analysis = MagicMock()
    analysis.analyze_search_results_batch.return_value = AnalysisBatchResult(
        events=[event],
        processed_count=1,
    )
    verification = MagicMock()
    verification.verify.return_value = _credibility(event.id)
    geo_service = MagicMock()
    geo_service.verify_and_match.return_value = geo
    matcher = MagicMock()
    matcher.match_event_to_network.return_value = MagicMock(
        matched_entity_ids=["entity-1"],
        downstream_entity_ids=[],
    )
    risk = MagicMock()
    risk.evaluate_risk.return_value = RiskAssessment(
        event_id=event.id,
        entity_id=entity.id,
        severity_score=72.0,
        factors={"dependency_weight_pct": 100.0},
        risk_level="high",
    )

    service = AlertService(
        network_service=network,
        research_service=research,
        analysis_service=analysis,
        matcher_service=matcher,
        risk_service=risk,
        verification_service=verification,
        geo_matching_service=geo_service,
    )

    result = await service.run_monitoring_cycle()

    matcher.match_event_to_network.assert_called_once_with(event, geo_result=geo)
    assert result["processed_results_count"] == 1
    assert result["extraction_success_count"] == 1
    assert result["extraction_failed_count"] == 0
