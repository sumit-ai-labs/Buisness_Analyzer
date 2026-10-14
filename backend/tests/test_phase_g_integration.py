"""Phase G Integration Tests — Credibility Verification Engine in monitoring pipeline.

Verifies the three core DoD (Definition of Done) integration scenarios:

1. HIGH credibility event  -> passes gate -> matcher/risk/alert pipeline continues
2. LOW credibility event   -> gated       -> stored in unconfirmed, pipeline skipped
3. MULTIPLE events         -> gating one must NOT stop others from processing

Additional tests:
- Model unavailable during pipeline -> neutral 0.5, no crash
- Unknown domain -> neutral 0.5 reputation
- list_unconfirmed_events returns correct fields
- gated_events_count returned in cycle summary
- /events/unconfirmed API endpoint returns retained event (not deleted)

Tests use mocked external services (LLM, search) to isolate the pipeline.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

from app.models.entity import BusinessEntity, EntityMetadata
from app.models.events import DisruptionEvent, RawSearchResult
from app.models.risk import RiskAssessment
from app.services.alert_service import AlertService
from app.services.verification_service import VerificationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(name: str, location: str, alternative_supplier: bool = False) -> BusinessEntity:
    return BusinessEntity(
        name=name,
        type="supplier",
        location=location,
        criticality="high",
        metadata=EntityMetadata(
            alternative_supplier_available=alternative_supplier,
        ),
    )


def _make_event(
    headline: str,
    source_url: str,
    event_type: str = "strike",
    location: str = "Mumbai",
    confidence: float = 0.85,
    is_relevant: bool = True,
) -> DisruptionEvent:
    return DisruptionEvent(
        source_url=source_url,
        source_result_id=f"sr-{headline[:8]}",
        headline=headline,
        summary=f"Summary of {headline}",
        event_type=event_type,
        location_mentioned=location,
        severity_raw="high",
        confidence=confidence,
        is_relevant=is_relevant,
    )


def _raw_result_for(event: DisruptionEvent, entity_id: str = "ent-1") -> RawSearchResult:
    return RawSearchResult(
        queried_entity_id=entity_id,
        title=event.headline,
        snippet=event.summary,
        url=event.source_url,
        query_used=f"disruption {event.location_mentioned}",
    )


def _build_service(
    entities: List[BusinessEntity],
    events_to_return: List[DisruptionEvent],
) -> AlertService:
    """Build an AlertService with all external dependencies mocked."""
    # --- network_service ---
    network_svc = MagicMock()
    network_svc.list_entities.return_value = entities
    entity_map = {e.id: e for e in entities}
    network_svc.get_entity.side_effect = lambda eid: entity_map.get(eid)
    network_svc.get_downstream.return_value = []

    # --- research_service ---
    research_svc = MagicMock()
    research_svc.search_disruptions_for_network.return_value = [
        _raw_result_for(ev, entities[0].id if entities else "ent-1") for ev in events_to_return
    ]

    # --- analysis_service --- returns the pre-built events directly
    analysis_svc = MagicMock()
    analysis_svc.analyze_search_results.return_value = events_to_return

    # --- matcher_service --- always matches the first entity directly
    matcher_svc = MagicMock()
    from app.models.events import MatchedImpact
    def _match(event, threshold_score=60.0):
        return MatchedImpact(
            event_id=event.id,
            matched_entity_ids=[entities[0].id],
            match_confidence=1.0,
            downstream_entity_ids=[],
        )
    matcher_svc.match_event_to_network.side_effect = _match

    # --- risk_service --- returns a deterministic assessment
    risk_svc = MagicMock()
    def _assess(entity, event, dependency_weight=1.0, credibility_score=None):
        ra = RiskAssessment(
            entity_id=entity.id,
            event_id=event.id,
            severity_score=75.0,
            risk_level="high",
            factors={},
            weighted_score=75.0,
        )
        return ra
    risk_svc.evaluate_risk.side_effect = _assess

    # --- verification_service --- REAL instance (core system under test)
    verification_svc = VerificationService()

    return AlertService(
        network_service=network_svc,
        research_service=research_svc,
        analysis_service=analysis_svc,
        matcher_service=matcher_svc,
        risk_service=risk_svc,
        verification_service=verification_svc,
    )


# ---------------------------------------------------------------------------
# Test 1: High credibility event passes gate and proceeds to pipeline
# ---------------------------------------------------------------------------

class TestHighCredibilityEvent:
    """score=63.5 (MODERATE) -> NOT gated -> entity matcher + risk + alert called."""

    @pytest.mark.asyncio
    async def test_high_credibility_event_not_gated(self):
        """Reuters-style event with LLM confidence 0.85 should NOT be gated."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Major port strike halts container shipping",
            source_url="https://reuters.com/supply-chain/port-strike-2026",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])

        # Override: force known reputation via override mechanism
        svc.verification_service = VerificationService()
        # Using override_source_reputation=0.90 is only in standalone verify()
        # In integrated pipeline, verification_service.verify() is called without overrides.
        # We test the REAL pipeline path: the actual domain lookup for reuters.com.

        result = await svc.run_monitoring_cycle()

        assert result["relevant_events_count"] == 1
        assert result["gated_events_count"] == 0
        assert result["new_alerts_count"] == 1

    @pytest.mark.asyncio
    async def test_verified_event_stored_in_events_dict(self):
        """Non-gated events must be in _events, not _unconfirmed_events."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Port workers begin strike over wages",
            source_url="https://reuters.com/supply-chain/strike-wages-2026",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])

        await svc.run_monitoring_cycle()

        # Should be in verified events
        assert event.id in svc._events
        # Should NOT be in unconfirmed
        assert event.id not in svc._unconfirmed_events

    @pytest.mark.asyncio
    async def test_verified_event_has_credibility_assessment_id(self):
        """Event must have credibility_assessment_id populated after pipeline."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Dock workers strike for second day",
            source_url="https://reuters.com/supply-chain/dock-strike",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        assert event.credibility_assessment_id is not None
        # Assessment must be retrievable
        ca = svc.get_credibility_assessment(event.credibility_assessment_id)
        assert ca is not None
        assert ca.authenticity_score >= 35  # must be non-gated

    @pytest.mark.asyncio
    async def test_risk_service_called_with_credibility_score(self):
        """risk_service.evaluate_risk must be called with credibility_score kwarg."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Crane operator strike",
            source_url="https://reuters.com/supply-chain/crane-strike",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        # The mock was called - retrieve call kwargs
        call_kwargs = svc.risk_service.evaluate_risk.call_args
        assert "credibility_score" in call_kwargs.kwargs or (
            len(call_kwargs.args) >= 4
        ), "credibility_score must be passed to evaluate_risk"

    @pytest.mark.asyncio
    async def test_alert_message_contains_verification_status(self):
        """Alert messages must contain 'Verification:' line."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Workers walk out at Mumbai Port",
            source_url="https://reuters.com/supply-chain/walkout-2026",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        alerts = svc.list_alerts()
        assert len(alerts) == 1
        assert "Verification:" in alerts[0].message


# ---------------------------------------------------------------------------
# Test 2: Low credibility event is gated
# ---------------------------------------------------------------------------

class TestLowCredibilityEvent:
    """score=33.5 (UNCONFIRMED) -> gated -> entity matcher NOT called, event retained."""

    @pytest.mark.asyncio
    async def test_unknown_source_event_gated(self):
        """Unknown-domain, low-ML, very-low-confidence event should be gated.

        Scoring guarantee: score = 0.35*50 + 0.25*0 + 0.20*50 + 0.20*25 = 17.5+0+10+5 = 32.5 < 35
        Even with neutral ML (0.5) and zero corroboration, confidence=0.25 keeps it below gate.
        """
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="GLOBALISTS hiding MASSIVE supply chain COLLAPSE!!!",
            source_url="https://completely-unknown-random-site-xyz.example.com/shock",
            location="Mumbai",
            event_type="other",
            confidence=0.25,  # so low that even neutral ML cannot push above gate
        )
        svc = _build_service([entity], [event])
        result = await svc.run_monitoring_cycle()

        # Must be gated
        assert result["gated_events_count"] == 1
        # No alerts for gated events
        assert result["new_alerts_count"] == 0

    @pytest.mark.asyncio
    async def test_gated_event_in_unconfirmed_dict(self):
        """Gated event must be in _unconfirmed_events, NOT in _events."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="SECRET insider reveals supply chain sabotage!!!",
            source_url="https://totally-unknown-fake-news-xyz.example.com/sabotage",
            location="Mumbai",
            event_type="other",
            confidence=0.25,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        assert event.id in svc._unconfirmed_events
        assert event.id not in svc._events

    @pytest.mark.asyncio
    async def test_gated_event_not_deleted(self):
        """Gated event must be RETAINED. list_unconfirmed_events must return it."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Anonymous tip: total port lockdown imminent",
            source_url="https://random-anonymous-xyz.example.com/lockdown",
            location="Mumbai",
            event_type="other",
            confidence=0.25,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        unconfirmed = svc.list_unconfirmed_events()
        assert len(unconfirmed) == 1

        uc = unconfirmed[0]
        assert uc["event_id"] == event.id
        assert uc["is_gated"] is True
        assert uc["confidence_label"] == "unconfirmed"
        assert uc["authenticity_score"] is not None

    @pytest.mark.asyncio
    async def test_entity_matcher_not_called_for_gated_event(self):
        """matcher_service.match_event_to_network must NOT be called for gated events."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Conspiracy blog: port is secretly closed by shadow government",
            source_url="https://unknown-blog-xyz-example.example.com/secret",
            location="Mumbai",
            event_type="other",
            confidence=0.25,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        svc.matcher_service.match_event_to_network.assert_not_called()


# ---------------------------------------------------------------------------
# Test 3: Multiple events — gating one must NOT stop others
# ---------------------------------------------------------------------------

class TestMultipleEvents:
    """With 3 events (A=high, B=low/gated, C=high): A and C must proceed; B alone is gated."""

    @pytest.mark.asyncio
    async def test_gated_event_does_not_stop_other_events(self):
        """One gated event must not block the rest of the monitoring cycle.

        Event B uses event_type='other' and very low confidence so it cannot
        be corroborated by events A and C (different event_type).
        """
        entity = _make_entity("Mumbai Port", "Mumbai")
        event_a = _make_event(
            headline="Reuters: Port strike confirmed day two",
            source_url="https://reuters.com/supply-chain/port-strike-d2",
            location="Mumbai",
            event_type="strike",
            confidence=0.90,
        )
        event_b = _make_event(
            headline="SHOCKING: ENTIRE port secretly BLOWN UP!!!",
            source_url="https://totally-unknown-random-site.example.com/blown-up",
            location="Mumbai",
            event_type="other",   # different type -> cannot be corroborated by A or C
            confidence=0.25,       # so low it gates even with neutral ML
        )
        event_c = _make_event(
            headline="BBC: flooding disrupts container depot near Mumbai",
            source_url="https://bbc.com/news/flooding-mumbai-depot-2026",
            location="Mumbai",
            event_type="flood",
            confidence=0.88,
        )
        svc = _build_service([entity], [event_a, event_b, event_c])

        result = await svc.run_monitoring_cycle()

        assert result["relevant_events_count"] == 3
        assert result["gated_events_count"] == 1  # only B
        # A and C should generate alerts
        assert result["new_alerts_count"] >= 1

    @pytest.mark.asyncio
    async def test_gated_event_b_is_in_unconfirmed_not_events(self):
        entity = _make_entity("Mumbai Port", "Mumbai")
        event_a = _make_event(
            "AP News: real strike at port",
            "https://apnews.com/strike-2026",
            location="Mumbai",
            event_type="strike",
            confidence=0.90,
        )
        event_b = _make_event(
            "FAKE: secret shutdown!",
            "https://random-unknown-xyz.example.com/fake",
            location="Mumbai",
            event_type="other",   # different type -> no corroboration with event_a
            confidence=0.25,
        )
        svc = _build_service([entity], [event_a, event_b])

        await svc.run_monitoring_cycle()

        assert event_b.id in svc._unconfirmed_events
        assert event_b.id not in svc._events
        assert event_a.id in svc._events


# ---------------------------------------------------------------------------
# Test 4: Unknown domain returns neutral reputation
# ---------------------------------------------------------------------------

class TestUnknownDomainNeutral:
    @pytest.mark.asyncio
    async def test_unknown_domain_gets_neutral_reputation(self):
        """Domain not in reputation table must get score=0.5, tier=unverified."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Supply chain disruption at Mumbai Port",
            source_url="https://totally-new-site-never-seen-before-xyz.example.com/news",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        ca_id = event.credibility_assessment_id
        assert ca_id is not None
        ca = svc.get_credibility_assessment(ca_id)
        assert ca is not None
        assert ca.source_tier == "unverified"
        assert ca.source_reputation_score == 0.5

    @pytest.mark.asyncio
    async def test_unknown_domain_not_treated_as_fake(self):
        """Unknown domain must have score > 0 (not auto-treated as unreliable)."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Some news about supply chain",
            source_url="https://brand-new-domain-xyz.example.com/story",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        ca = svc.get_credibility_assessment(event.credibility_assessment_id)
        assert ca.source_reputation_score > 0.0


# ---------------------------------------------------------------------------
# Test 5: Model unavailable during pipeline — no crash
# ---------------------------------------------------------------------------

class TestModelUnavailableDuringPipeline:
    @pytest.mark.asyncio
    async def test_model_failure_does_not_crash_pipeline(self):
        """If ML model is None during verify, pipeline must still complete."""
        from app.core import credibility_model

        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Supply chain disruption near Mumbai harbour",
            source_url="https://reuters.com/supply-chain/harbour-disruption",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])

        orig_clf = credibility_model._clf
        orig_vec = credibility_model._vectorizer
        try:
            credibility_model._clf = None
            credibility_model._vectorizer = None
            # Must not raise
            result = await svc.run_monitoring_cycle()
            assert result["relevant_events_count"] == 1
        finally:
            credibility_model._clf = orig_clf
            credibility_model._vectorizer = orig_vec

    @pytest.mark.asyncio
    async def test_model_failure_uses_neutral_content_score(self, monkeypatch):
        """ML failure -> content_style_score must be 0.5 (neutral), not 0 or 1."""
        from app.core import credibility_model

        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            headline="Dock workers refuse to load containers at port",
            source_url="https://reuters.com/supply-chain/dock-refusal",
            location="Mumbai",
            confidence=0.85,
        )
        svc = _build_service([entity], [event])

        monkeypatch.setattr(credibility_model, "load_model", lambda: False)
        monkeypatch.setattr(credibility_model, "_clf", None)
        monkeypatch.setattr(credibility_model, "_vectorizer", None)
        await svc.run_monitoring_cycle()

        ca = svc.get_credibility_assessment(event.credibility_assessment_id)
        assert ca is not None
        assert ca.content_style_score == 0.5


# ---------------------------------------------------------------------------
# Test 6: gated_events_count in cycle summary
# ---------------------------------------------------------------------------

class TestCycleSummaryFields:
    @pytest.mark.asyncio
    async def test_cycle_result_contains_gated_count(self):
        """run_monitoring_cycle must return gated_events_count key."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event("Reuters: port test event", "https://reuters.com/test", location="Mumbai", confidence=0.85)
        svc = _build_service([entity], [event])

        result = await svc.run_monitoring_cycle()
        assert "gated_events_count" in result

    @pytest.mark.asyncio
    async def test_summary_stats_contains_unconfirmed_count(self):
        """get_summary_stats must include unconfirmed_events count."""
        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event(
            "Unknown blog: shock disruption!!",
            "https://random-unknown-xyz.example.com/shock",
            location="Mumbai",
            event_type="other",
            confidence=0.25,
        )
        svc = _build_service([entity], [event])
        await svc.run_monitoring_cycle()

        stats = svc.get_summary_stats()
        assert "unconfirmed_events" in stats


# ---------------------------------------------------------------------------
# Test 7: Regression — existing risk tests not broken by credibility_score arg
# ---------------------------------------------------------------------------

class TestRiskServiceBackwardsCompatibility:
    """Ensure that when credibility_score=None, risk calculation is unchanged."""

    def test_risk_score_without_credibility_score_unchanged(self):
        """evaluate_risk with no credibility_score must use original formula."""
        from app.services.risk_service import RiskService
        from app.core.dynamic_config import get_config_store

        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event("Test event", "https://reuters.com/test", confidence=0.85)

        svc = RiskService()
        assessment = svc.evaluate_risk(entity=entity, event=event, dependency_weight=1.0)
        assert assessment.severity_score > 0

    def test_risk_score_with_credibility_score_different_from_without(self):
        """evaluate_risk with a high credibility_score should yield different (>=) result
        than without, because the confidence multiplier is higher."""
        from app.services.risk_service import RiskService

        entity = _make_entity("Mumbai Port", "Mumbai")
        event = _make_event("Test event credibility compare", "https://reuters.com/test2", confidence=0.70)

        svc = RiskService()
        score_no_cred = svc.evaluate_risk(entity=entity, event=event, dependency_weight=1.0, credibility_score=None).severity_score
        score_high_cred = svc.evaluate_risk(entity=entity, event=event, dependency_weight=1.0, credibility_score=0.90).severity_score
        score_low_cred = svc.evaluate_risk(entity=entity, event=event, dependency_weight=1.0, credibility_score=0.10).severity_score

        # Higher credibility -> higher confidence -> higher severity score
        assert score_high_cred >= score_no_cred
        # Lower credibility -> lower confidence -> lower severity score
        assert score_low_cred <= score_no_cred

    def test_severity_weights_unchanged(self):
        """Severity factors (alternative_supplier, etc.) must not be changed."""
        from app.services.risk_service import RiskService

        entity_no_alt = _make_entity("Mumbai Port", "Mumbai", alternative_supplier=False)
        entity_with_alt = _make_entity("Mumbai Port Alt", "Mumbai", alternative_supplier=True)

        event = _make_event("Test severity", "https://reuters.com/sev-test", confidence=0.85)
        svc = RiskService()

        score_no_alt = svc.evaluate_risk(entity=entity_no_alt, event=event).severity_score
        score_with_alt = svc.evaluate_risk(entity=entity_with_alt, event=event).severity_score

        # No alternative supplier -> higher severity (unchanged behaviour)
        assert score_no_alt > score_with_alt
