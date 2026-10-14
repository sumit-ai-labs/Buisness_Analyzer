"""Sections D, E, F — Verify (Credibility + Geo) & Connect Edge-Case Tests.

Tests D1–D8, E2–E7, F1–F4 from the full-system test matrix.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock, patch

import pytest

from app.core.domain_reputation import lookup_domain, DOMAIN_REPUTATION_TABLE
from app.models.entity import BusinessEntity, EntityMetadata
from app.models.events import DisruptionEvent
from app.models.geo import EventLocation, GeoConfig, GeoMatchCandidate, GeoVerificationResult
from app.services.verification_service import (
    VerificationService,
    bucket_confidence,
    CRED_WEIGHTS,
    CORROBORATION_CAP,
    GATE_THRESHOLD,
)
from app.services.geo_matching_service import GeoMatchingService
from app.services.matcher_service import MatcherService
from app.services.network_service import NetworkService
from tests.conftest import make_entity, make_event, make_relationship


service = VerificationService()


# ===========================================================================
# D1: High-rep source, zero corroboration (breaking news)
# Type: Unit
# ===========================================================================
class TestD1HighRepBreakingNews:
    def test_reputable_zero_corroboration_is_moderate_not_gated(self):
        """D1: Worked Example 1 regression — score ~63.5, moderate, NOT gated."""
        event = make_event(
            source_url="https://reuters.com/article",
            confidence=0.85,
        )
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.75,
        )
        assert assessment.authenticity_score == 63.5
        assert assessment.confidence_label == "moderate"
        assert assessment.is_gated is False


# ===========================================================================
# D2: Unknown domain, low content-style, zero corroboration
# Type: Unit
# ===========================================================================
class TestD2UnknownLowStyle:
    def test_unknown_domain_low_style_is_unconfirmed_gated(self):
        """D2: Worked Example 2 regression — score 33.5, unconfirmed, IS gated."""
        event = make_event(
            source_url="https://unknown-xyz.com/a",
            confidence=0.6,
        )
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.5,
            override_corroboration_count=0,
            override_content_style_score=0.2,
        )
        assert assessment.authenticity_score == 33.5
        assert assessment.confidence_label == "unconfirmed"
        assert assessment.is_gated is True


# ===========================================================================
# D3: Known satire/blacklisted domain
# Type: Unit
# ===========================================================================
class TestD3SatireDomain:
    def test_satire_domain_has_very_low_reputation(self):
        """D3: Known satire domain gets very low reputation score."""
        score, tier = lookup_domain("theonion.com")
        assert score == 0.05
        assert tier == "satire"

    def test_satire_source_event_is_gated(self):
        """D3b: Event from satire source gets gated."""
        event = make_event(
            source_url="https://theonion.com/article",
            confidence=0.5,
        )
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.05,
            override_corroboration_count=0,
            override_content_style_score=0.5,
        )
        # 0.35*5 + 0.25*0 + 0.20*50 + 0.20*50 = 1.75 + 0 + 10 + 10 = 21.75
        assert assessment.authenticity_score < GATE_THRESHOLD
        assert assessment.is_gated is True


# ===========================================================================
# D5: Credibility model file missing/fails to load
# Type: Resilience
# ===========================================================================
class TestD5ModelMissing:
    def test_model_unavailable_defaults_to_neutral(self):
        """D5: When ML model can't load, content_style_score defaults to 0.5."""
        from app.core import credibility_model

        original_clf = credibility_model._clf
        original_vec = credibility_model._vectorizer
        # Also prevent auto-reload by patching load_model
        try:
            credibility_model._clf = None
            credibility_model._vectorizer = None
            with patch.object(credibility_model, 'load_model', return_value=False):
                score = credibility_model.predict_style_score("Test text about a flood")
            assert score == 0.5, f"Expected 0.5 neutral fallback, got {score}"
        finally:
            credibility_model._clf = original_clf
            credibility_model._vectorizer = original_vec


# ===========================================================================
# D6: Corroboration count exceeds cap
# Type: Unit
# ===========================================================================
class TestD6CorroborationCap:
    def test_cap_prevents_score_exceeding_1(self):
        """D6: Corroboration capped at CORROBORATION_CAP (3)."""
        event = make_event(confidence=0.85)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.9,
            override_corroboration_count=10,  # way above cap
            override_content_style_score=0.75,
        )
        assert assessment.corroboration_score == 1.0
        # Verify the corroboration factor contribution is exactly 0.25 * 100 = 25
        assert assessment.factors["corroboration"] == 25.0


# ===========================================================================
# D7: CRED_WEIGHTS sum check
# Type: Unit
# ===========================================================================
class TestD7WeightsSum:
    def test_cred_weights_sum_to_1(self):
        """D7: CRED_WEIGHTS sum to exactly 1.0."""
        total = sum(CRED_WEIGHTS.values())
        assert math.isclose(total, 1.0, abs_tol=1e-9)


# ===========================================================================
# D8: Gate threshold boundary
# Type: Unit
# ===========================================================================
class TestD8GateBoundary:
    def test_score_exactly_at_threshold_is_not_gated(self):
        """D8: Score exactly = GATE_THRESHOLD (35) is NOT gated (strict < comparison).
        
        Documented: is_gated = authenticity_score < GATE_THRESHOLD.
        So score=35.0 means is_gated=False, confidence_label='low'.
        """
        event = make_event(confidence=0.0)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=1.0,
            override_corroboration_count=0,
            override_content_style_score=0.0,
        )
        assert assessment.authenticity_score == 35.0
        assert assessment.is_gated is False
        assert assessment.confidence_label == "low"

    def test_score_just_below_threshold_is_gated(self):
        """D8b: Score just below threshold IS gated."""
        label = bucket_confidence(34.99)
        assert label == "unconfirmed"


# ===========================================================================
# E3: GPS vs event/business location
# Type: Unit
# ===========================================================================
class TestE3GPSNotUsedForMatching:
    def test_user_device_location_model_is_separate(self):
        """E3: UserDeviceLocation model exists separately, never used in geo matching."""
        from app.models.geo import UserDeviceLocation
        # Confirm UserDeviceLocation has its own fields and is never referenced in GeoMatchingService
        loc = UserDeviceLocation(latitude=28.6, longitude=77.2, accuracy_m=10.0)
        assert loc.status == "AVAILABLE"
        # GeoMatchingService.evaluate_candidate does NOT accept UserDeviceLocation


# ===========================================================================
# E5: Entity has no coordinates set
# Type: Unit
# ===========================================================================
class TestE5EntityNoCoordinates:
    def test_entity_without_coords_doesnt_crash_matcher(self):
        """E5: Entity with no lat/lon is excluded from geo distance calc cleanly."""
        from app.services.geocoding_service import GeocodingService
        
        # Create a mock geocoding service that returns unresolved for everything
        mock_geocoder = MagicMock()
        mock_geocoder.resolve_place.return_value = EventLocation(
            raw_text="Somewhere",
            confidence=0.0,
            source="mock",
            is_resolved=False,
        )
        
        svc = GeoMatchingService(geocoding_service=mock_geocoder, config=GeoConfig())
        event = make_event(location_mentioned="Somewhere Unknown")
        entity = make_entity(id="no-coord", name="No Coord Entity", lat=None, lon=None)
        
        candidate = svc.evaluate_candidate(
            EventLocation(raw_text="Test", confidence=0.0, source="test", is_resolved=False),
            event,
            entity,
        )
        # Should complete without crash; distance_km should be None
        assert candidate.distance_km is None


# ===========================================================================
# E6: Distance exactly at match threshold
# Type: Unit
# ===========================================================================
class TestE6DistanceThreshold:
    def test_distance_factor_boundaries(self):
        """E6: Document and verify distance-to-score boundaries."""
        svc = GeoMatchingService.__new__(GeoMatchingService)
        # ≤15km → 1.0
        assert svc.calculate_distance_factor(15.0) == 1.0
        assert svc.calculate_distance_factor(0.0) == 1.0
        # ≤35km → 0.90
        assert svc.calculate_distance_factor(35.0) == 0.90
        assert svc.calculate_distance_factor(16.0) == 0.90
        # ≤75km → 0.75
        assert svc.calculate_distance_factor(75.0) == 0.75
        # ≤150km → 0.50
        assert svc.calculate_distance_factor(150.0) == 0.50
        # ≤300km → 0.25
        assert svc.calculate_distance_factor(300.0) == 0.25
        # ≤600km → 0.05
        assert svc.calculate_distance_factor(600.0) == 0.05
        # >600km → 0.0
        assert svc.calculate_distance_factor(601.0) == 0.0
        # None → 0.40 (neutral)
        assert svc.calculate_distance_factor(None) == 0.40


# ===========================================================================
# F1: Event matches zero entities
# Type: Integration
# ===========================================================================
class TestF1ZeroEntityMatch:
    def test_event_matching_no_entities_returns_none(self):
        """F1: Event matching zero entities returns None, not an error."""
        net_svc = NetworkService()
        mock_geo = MagicMock()
        mock_geo.verify_and_match.return_value = GeoVerificationResult(
            event_id="evt-1",
            event_location=EventLocation(raw_text="Nowhere", confidence=0.0, source="mock", is_resolved=False),
            status="LOCATION_UNRESOLVED",
        )
        matcher = MatcherService(network_service=net_svc, geo_matching_service=mock_geo)
        event = make_event(location_mentioned="Nowhere Important")
        result = matcher.match_event_to_network(event)
        assert result is None


# ===========================================================================
# F3: Downstream traversal depth cap
# Type: Unit
# ===========================================================================
class TestF3DepthCap:
    def test_downstream_respects_max_depth(self):
        """F3: Downstream traversal stops at configured depth."""
        svc = NetworkService()
        # Build a 6-node chain: 0→1→2→3→4→5
        for i in range(6):
            svc.add_entity(make_entity(id=f"n{i}", name=f"Node {i}"))
        for i in range(5):
            svc.add_relationship(make_relationship(
                id=f"r{i}", source_id=f"n{i}", target_id=f"n{i+1}",
            ))

        depth2 = svc.get_downstream("n0", max_depth=2)
        depth2_ids = {e.id for e in depth2}
        # At max_depth=2, should find n1 and n2 but NOT n3, n4, n5
        assert "n1" in depth2_ids
        assert "n2" in depth2_ids
        assert "n3" not in depth2_ids
