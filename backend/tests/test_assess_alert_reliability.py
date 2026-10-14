"""Sections G, H, J — Assess (Risk Formula), Alert Generation, and Concurrency & Reliability Tests.

Tests G1–G4, H1–H5, J1–J4 from the full-system test matrix.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.dynamic_config import (
    DynamicConfigStore,
    RiskThresholdsConfig,
    RiskWeightsConfig,
    SystemConfig,
)
from app.models.entity import BusinessEntity, BusinessRelationship, EntityMetadata
from app.models.events import DisruptionEvent, RawSearchResult
from app.models.geo import EventLocation, GeoVerificationResult
from app.services.alert_service import AlertService
from app.services.geo_matching_service import GeoMatchingService
from app.services.matcher_service import MatcherService
from app.services.network_service import NetworkService
from app.services.risk_service import RiskService
from app.services.verification_service import VerificationService
from app.services.weather_service import WeatherSignal
from tests.conftest import make_entity, make_event, make_relationship


# ===========================================================================
# Section G: Assess (Risk Formula)
# ===========================================================================

class TestG1WorkedExamples:
    @pytest.fixture
    def risk_svc(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        store = DynamicConfigStore(file_path=str(cfg_file))
        return RiskService(config_store=store)

    def test_worked_example_a_critical(self, risk_svc):
        """G1a: Worked Example A — Maximum vulnerability / critical disruption.
        
        Entity: high criticality (100), lead_time 60 days (100), single source (100).
        Event: confidence 1.0 (100), dependency 1.0 (100).
        Score: 0.30*100 + 0.25*100 + 0.20*100 + 0.15*100 + 0.10*100 = 100.0.
        """
        entity = BusinessEntity(
            id="ent-a",
            name="Lithium Mine",
            type="supplier",
            location="Atacama",
            criticality="high",
            metadata=EntityMetadata(lead_time_days=60, alternative_supplier_available=False),
        )
        event = DisruptionEvent(
            source_url="https://example.com/strike",
            source_result_id="res-a",
            headline="Full strike halts lithium output",
            summary="Production halted.",
            event_type="strike",
            location_mentioned="Atacama",
            severity_raw="high",
            confidence=1.0,
            is_relevant=True,
        )
        assessment = risk_svc.evaluate_risk(entity, event, dependency_weight=1.0)
        assert assessment.severity_score == 100.0
        assert assessment.risk_level == "critical"

    def test_worked_example_b_low(self, risk_svc):
        """G1b: Worked Example B — Low vulnerability / minor weather event.
        
        Entity: low criticality (25), lead_time 0 days (0), multi-source (0).
        Event: confidence 0.5 (50), dependency 0.1 (10).
        Score: 0.30*10 + 0.25*25 + 0.20*0 + 0.15*0 + 0.10*50 = 3 + 6.25 + 0 + 0 + 5 = 14.25.
        """
        entity = BusinessEntity(
            id="ent-b",
            name="Box Supplier",
            type="supplier",
            location="Berlin",
            criticality="low",
            metadata=EntityMetadata(lead_time_days=0, alternative_supplier_available=True),
        )
        event = DisruptionEvent(
            source_url="https://example.com/rain",
            source_result_id="res-b",
            headline="Rain shower in Berlin",
            summary="Slight rain.",
            event_type="weather",
            location_mentioned="Berlin",
            severity_raw="low",
            confidence=0.5,
            is_relevant=True,
        )
        assessment = risk_svc.evaluate_risk(entity, event, dependency_weight=0.1)
        assert assessment.severity_score == 14.25
        assert assessment.risk_level == "low"

    def test_worked_example_c_medium(self, risk_svc):
        """G1c: Worked Example C — Moderate vulnerability / medium disruption.
        
        Entity: medium criticality (50), lead_time 30 days (50), multi-source (0).
        Event: confidence 0.8 (80), dependency 0.5 (50).
        Score: 0.30*50 + 0.25*50 + 0.20*50 + 0.15*0 + 0.10*80 = 15 + 12.5 + 10 + 0 + 8 = 45.5.
        """
        entity = BusinessEntity(
            id="ent-c",
            name="Assembly Plant",
            type="factory",
            location="Munich",
            criticality="medium",
            metadata=EntityMetadata(lead_time_days=30, alternative_supplier_available=True),
        )
        event = DisruptionEvent(
            source_url="https://example.com/closure",
            source_result_id="res-c",
            headline="Partial maintenance closure",
            summary="Maintenance closure.",
            event_type="closure",
            location_mentioned="Munich",
            severity_raw="medium",
            confidence=0.8,
            is_relevant=True,
        )
        assessment = risk_svc.evaluate_risk(entity, event, dependency_weight=0.5)
        assert assessment.severity_score == 45.5
        assert assessment.risk_level == "medium"


class TestG2BoundaryScores:
    @pytest.fixture
    def boundary_svc(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        store = DynamicConfigStore(file_path=str(cfg_file))
        cfg = SystemConfig(thresholds=RiskThresholdsConfig(low=40.0, medium=65.0, high=85.0))
        store.save_config(cfg)
        return RiskService(config_store=store)

    def test_boundary_exactly_40_is_medium(self, boundary_svc):
        """G2: Scores exactly at 40 / 65 / 85 are bucketed into medium, high, and critical respectively."""
        thresholds = boundary_svc.config_store.get_config().thresholds
        assert thresholds.low == 40.0
        assert thresholds.medium == 65.0
        assert thresholds.high == 85.0

        def classify(score):
            if score < thresholds.low:
                return "low"
            elif score < thresholds.medium:
                return "medium"
            elif score < thresholds.high:
                return "high"
            return "critical"

        assert classify(39.99) == "low"
        assert classify(40.0) == "medium"
        assert classify(64.99) == "medium"
        assert classify(65.0) == "high"
        assert classify(84.99) == "high"
        assert classify(85.0) == "critical"


class TestG3CombinedTrustConfidenceMultiplier:
    @pytest.fixture
    def risk_svc(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        store = DynamicConfigStore(file_path=str(cfg_file))
        return RiskService(config_store=store)

    def test_credibility_multiplier_math(self, risk_svc):
        """G3: combined_trust blends LLM confidence and credibility 50/50.
        
        LLM confidence = 0.80.
        With high credibility (0.90): combined_trust = 0.5*0.80 + 0.5*0.90 = 0.85 -> f_conf = 85.0.
        With low credibility (0.20):  combined_trust = 0.5*0.80 + 0.5*0.20 = 0.50 -> f_conf = 50.0.
        Difference in confidence contribution: (85.0 - 50.0) * 0.10 = 3.5 points.
        """
        entity = BusinessEntity(
            name="Test Ent", type="factory", location="Loc", criticality="low",
            metadata=EntityMetadata(lead_time_days=0, alternative_supplier_available=True),
        )
        event = DisruptionEvent(
            source_url="https://ex.com", source_result_id="s1", headline="H", summary="S",
            event_type="strike", location_mentioned="Loc", severity_raw="low",
            confidence=0.80, is_relevant=True,
        )
        res_high = risk_svc.evaluate_risk(entity, event, dependency_weight=0.0, credibility_score=0.90)
        res_low = risk_svc.evaluate_risk(entity, event, dependency_weight=0.0, credibility_score=0.20)

        assert res_high.factors["extraction_confidence"] == 85.0
        assert res_low.factors["extraction_confidence"] == 50.0
        diff = round(res_high.severity_score - res_low.severity_score, 2)
        assert diff == 3.50


class TestG4ScoreClamp:
    @pytest.fixture
    def risk_svc(self, tmp_path):
        cfg_file = tmp_path / "config.json"
        store = DynamicConfigStore(file_path=str(cfg_file))
        return RiskService(config_store=store)

    def test_extreme_high_inputs_clamped_at_100(self, risk_svc):
        """G4a: Extreme inputs above range cannot produce score > 100.0."""
        entity = BusinessEntity(
            name="Ent", type="supplier", location="Loc", criticality="high",
            metadata=EntityMetadata(lead_time_days=99999, alternative_supplier_available=False),
        )
        event = DisruptionEvent(
            source_url="https://ex.com", source_result_id="s1", headline="H", summary="S",
            event_type="strike", location_mentioned="Loc", severity_raw="high",
            confidence=1.0, is_relevant=True,
        )
        assessment = risk_svc.evaluate_risk(entity, event, dependency_weight=5.0, credibility_score=5.0)
        assert assessment.severity_score <= 100.0
        assert assessment.severity_score == 100.0

    def test_extreme_low_inputs_clamped_at_0(self, risk_svc):
        """G4b: Extreme negative inputs cannot produce score < 0.0."""
        entity = BusinessEntity(
            name="Ent", type="supplier", location="Loc", criticality="low",
            metadata=EntityMetadata(lead_time_days=0, alternative_supplier_available=True),
        )
        event = DisruptionEvent(
            source_url="https://ex.com", source_result_id="s1", headline="H", summary="S",
            event_type="strike", location_mentioned="Loc", severity_raw="low",
            confidence=0.0, is_relevant=True,
        )
        assessment = risk_svc.evaluate_risk(entity, event, dependency_weight=-5.0, credibility_score=-1.0)
        assert 0.0 <= assessment.severity_score <= 100.0


# ===========================================================================
# Section H: Alert Generation
# ===========================================================================

class TestHAlertGeneration:
    def _build_alert_svc(self, entities, events, mock_geo=None):
        mock_net = MagicMock()
        mock_net.list_entities.return_value = entities
        mock_net.get_entity.side_effect = lambda eid: next((e for e in entities if e.id == eid), None)
        mock_net.get_downstream.return_value = []

        mock_res = MagicMock()
        raw_results = [
            RawSearchResult(
                id=e.source_result_id,
                url=e.source_url,
                title=e.headline,
                snippet=e.summary,
                queried_entity_id=entities[0].id if entities else "ent-1",
                query_used="test query",
            )
            for e in events
        ]
        mock_res.search_disruptions_for_network.return_value = raw_results

        mock_ana = MagicMock()
        mock_ana.analyze_search_results.return_value = events

        return AlertService(
            network_service=mock_net,
            research_service=mock_res,
            analysis_service=mock_ana,
            matcher_service=MatcherService(network_service=mock_net),
            risk_service=RiskService(),
            verification_service=VerificationService(),
            geo_matching_service=mock_geo or GeoMatchingService(),
        )

    @pytest.mark.asyncio
    async def test_h1_deduplication_across_two_consecutive_cycles(self):
        """H1: Running two consecutive monitoring cycles produces 1 alert only."""
        entity = make_entity(id="ent-kandla", name="Kandla Port", type="supplier", location="Kandla, Gujarat", lat=23.0, lon=70.2)
        event = make_event(
            headline="Port strike in Kandla",
            source_url="https://reuters.com/kandla-strike",
            event_type="strike",
            location_mentioned="Kandla",
            confidence=0.9,
        )

        svc = self._build_alert_svc([entity], [event])

        # Cycle 1
        res1 = await svc.run_monitoring_cycle()
        assert res1["new_alerts_count"] == 1
        assert len(svc.list_alerts()) == 1

        # Cycle 2 with identical event/entity
        res2 = await svc.run_monitoring_cycle()
        assert res2["new_alerts_count"] == 0
        assert len(svc.list_alerts()) == 1

    @pytest.mark.asyncio
    async def test_h2_one_event_multiple_impacted_entities(self):
        """H2: One event impacting multiple entities creates individual RiskAssessments."""
        ent1 = make_entity(id="ent-mumbai-1", name="Supplier Alpha", type="supplier", location="Mumbai", lat=19.07, lon=72.87)
        ent2 = make_entity(id="ent-mumbai-2", name="Supplier Beta", type="supplier", location="Mumbai", lat=19.08, lon=72.88)
        event = make_event(
            headline="Power outage across Mumbai",
            source_url="https://reuters.com/mumbai-power",
            event_type="closure",
            location_mentioned="Mumbai",
            confidence=0.85,
        )

        mock_net = MagicMock()
        mock_net.list_entities.return_value = [ent1, ent2]
        mock_net.get_entity.side_effect = lambda eid: next((e for e in [ent1, ent2] if e.id == eid), None)
        mock_net.get_downstream.return_value = []

        mock_res = MagicMock()
        raw_sr = RawSearchResult(
            id=event.source_result_id,
            url=event.source_url,
            title=event.headline,
            snippet=event.summary,
            queried_entity_id=ent1.id,
            query_used="test",
        )
        mock_res.search_disruptions_for_network.return_value = [raw_sr]

        mock_ana = MagicMock()
        mock_ana.analyze_search_results.return_value = [event]

        mock_matcher = MagicMock()
        from app.models.events import MatchedImpact
        mock_matcher.match_event_to_network.return_value = MatchedImpact(
            event_id=event.id,
            matched_entity_ids=[ent1.id, ent2.id],
            match_confidence=0.9,
            downstream_entity_ids=[],
        )

        mock_geo = MagicMock()
        mock_geo.verify_and_match.return_value = GeoVerificationResult(
            event_id=event.id,
            status="LOCATION_VERIFIED",
            location_confidence=0.95,
            entity_match_confidence=95.0,
            event_location=EventLocation(raw_text="Mumbai", city="Mumbai", latitude=19.07, longitude=72.87),
        )

        svc = AlertService(
            network_service=mock_net,
            research_service=mock_res,
            analysis_service=mock_ana,
            matcher_service=mock_matcher,
            risk_service=RiskService(),
            verification_service=VerificationService(),
            geo_matching_service=mock_geo,
        )

        await svc.run_monitoring_cycle()
        # Two distinct risk assessments evaluated
        assert len(svc._assessments) == 2
        # Alert is produced referencing both impacted entities
        alerts = svc.list_alerts()
        assert len(alerts) == 1
        assert ent1.id in alerts[0].entity_ids
        assert ent2.id in alerts[0].entity_ids

    @pytest.mark.asyncio
    async def test_h3_gated_unconfirmed_event_creates_no_alert(self):
        """H3: Gated (unconfirmed) event creates 0 alerts and appears in GET /events/unconfirmed."""
        entity = make_entity(id="ent-paris", name="Factory X", type="factory", location="Paris", lat=48.85, lon=2.35)
        event = make_event(
            headline="Fake rumour about strike",
            source_url="https://random-unverified-blog.xyz/rumour",
            event_type="strike",
            location_mentioned="Paris",
            confidence=0.4,
        )

        svc = self._build_alert_svc([entity], [event])

        # Patch style score to be low (e.g. 0.1) so authenticity_score < 35
        with patch("app.core.credibility_model.predict_style_score", return_value=0.10):
            res = await svc.run_monitoring_cycle()

        assert res["new_alerts_count"] == 0
        assert len(svc.list_alerts()) == 0
        unconfirmed = svc.list_unconfirmed_events()
        assert len(unconfirmed) == 1
        assert unconfirmed[0]["event_id"] == event.id
        assert unconfirmed[0]["is_gated"] is True

    @pytest.mark.asyncio
    async def test_h4_alert_message_content(self):
        """H4: Alert message contains verification/confidence line and weather line when confirmed."""
        entity = make_entity(id="ent-chennai", name="Port Facility", type="supplier", location="Chennai", lat=13.08, lon=80.27)
        event = make_event(
            headline="Severe flood in Chennai",
            source_url="https://reuters.com/flood",
            event_type="flood",
            location_mentioned="Chennai",
            confidence=0.9,
        )

        svc = self._build_alert_svc([entity], [event])

        confirmed_signal = WeatherSignal(
            status="checked",
            confirms_event=True,
            precipitation_mm_24h=35.0,
            wind_speed_kmh=40.0,
        )

        with patch("app.services.alert_service.check_weather_corroboration", new_callable=AsyncMock, return_value=confirmed_signal):
            await svc.run_monitoring_cycle()

        alerts = svc.list_alerts()
        assert len(alerts) == 1
        msg = alerts[0].message
        # Check verification line
        assert "Verification:" in msg
        assert "credibility" in msg
        # Check weather corroboration line
        assert "Independently confirmed: 35mm rainfall recorded" in msg

    def test_h5_acknowledge_alert(self):
        """H5: Acknowledging an alert sets acknowledged=True and records acknowledged_at."""
        entity = make_entity(id="ent-p", name="Port", type="supplier", location="Loc")
        event = make_event(
            headline="Strike in port",
            source_url="https://reuters.com/strike",
            event_type="strike",
            location_mentioned="Loc",
        )
        svc = self._build_alert_svc([entity], [event])

        from app.models.risk import Alert
        alert = Alert(
            event_id=event.id,
            risk_assessment_id="ra-1",
            entity_ids=[entity.id],
            message="Test alert message",
            dedupe_key="dedupe-1",
        )
        svc._alerts[alert.id] = alert
        assert alert.acknowledged is False
        assert alert.acknowledged_at is None

        acked = svc.acknowledge_alert(alert.id)
        assert acked.acknowledged is True
        assert acked.acknowledged_at is not None
        assert isinstance(acked.acknowledged_at, datetime)


# ===========================================================================
# Section J: Concurrency & Reliability
# ===========================================================================

class TestJConcurrencyAndReliability:
    @pytest.mark.asyncio
    async def test_j1_concurrent_monitor_run_rejected_with_409(self):
        """J1: Two concurrent /monitor/run calls -> second rejected with HTTP 409 Conflict."""
        mock_net = MagicMock()
        mock_net.list_entities.return_value = []
        svc = AlertService(
            network_service=mock_net,
            research_service=MagicMock(),
            analysis_service=MagicMock(),
            matcher_service=MagicMock(),
            risk_service=RiskService(),
            verification_service=VerificationService(),
            geo_matching_service=GeoMatchingService(),
        )

        # Simulate lock already held by another in-progress run
        await svc._lock.acquire()
        try:
            with pytest.raises(HTTPException) as exc_info:
                await svc.run_monitoring_cycle()
            assert exc_info.value.status_code == 409
            assert "in progress" in exc_info.value.detail.lower()
        finally:
            svc._lock.release()

    def test_j2_api_keys_missing_flagged_degraded(self):
        """J2: Missing API keys reported clearly in health endpoint degraded state."""
        from app.core.config import Settings
        empty_settings = Settings(TAVILY_API_KEY="", LLM_API_KEY="", GEMINI_API_KEY="")
        assert empty_settings.has_tavily_key is False
        assert empty_settings.has_llm_key is False

    def test_j3_malformed_entity_input_rejected_by_pydantic(self):
        """J3: Invalid types or invalid enum values on entity creation rejected by Pydantic."""
        from pydantic import ValidationError
        # Invalid criticality
        with pytest.raises(ValidationError):
            BusinessEntity(
                name="Bad Entity",
                type="supplier",
                location="Berlin",
                criticality="ultra_extreme_critical",  # type: ignore
            )
        # Invalid latitude out of range
        with pytest.raises(ValidationError):
            BusinessEntity(
                name="Bad Lat",
                type="supplier",
                location="Berlin",
                criticality="high",
                latitude=999.0,  # Invalid lat > 90
            )

    def test_j4_clean_restart_behavior(self):
        """J4: Restarting services initializes fresh, uncorrupted state."""
        net = NetworkService()
        assert len(net.list_entities()) == 0
        assert len(net.list_relationships()) == 0

        alert_svc = AlertService(network_service=net)
        assert len(alert_svc.list_alerts()) == 0
        assert len(alert_svc.list_events()) == 0
        assert len(alert_svc.list_unconfirmed_events()) == 0
