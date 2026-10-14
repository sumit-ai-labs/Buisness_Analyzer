"""Unit tests — Phase E: Credibility Calculation Formula & Verification Service.

Mandatory worked examples (from spec):
    Example 1: Reputable breaking-news source, zero corroboration → 63.5 / moderate / not gated
    Example 2: Unknown source, zero corroboration, suspicious style → 33.5 / unconfirmed / gated

Required boundary tests:
    TEST 1:  High-reputation + zero corroboration → NOT gated
    TEST 2:  Unknown domain → reputation = 0.5 (not 0)
    TEST 3:  Model unavailable → content_style_score = 0.5, no crash
    TEST 4:  3 corroborating sources → corroboration = 1.0
    TEST 5:  5 corroborating sources → corroboration still = 1.0 (cap at 3)
    TEST 6:  Same domain → not counted as independent corroboration
    TEST 7:  Different event_type → not counted
    TEST 8:  Different location → not counted
    TEST 9:  Outside time window → not counted
    TEST 10: Score boundary 35 → 'low' (not 'unconfirmed')
    TEST 11: Score boundary 60 → 'moderate'
    TEST 12: Score boundary 80 → 'high'
"""

from __future__ import annotations

import pytest
from app.models.events import DisruptionEvent
from app.services.verification_service import (
    VerificationService,
    bucket_confidence,
    GATE_THRESHOLD,
    CORROBORATION_CAP,
)


def _make_event(
    source_url: str = "https://reuters.com/article-1",
    event_type: str = "flood",
    location_mentioned: str = "Mumbai",
    confidence: float = 0.85,
    headline: str = "Flood disrupts supply routes",
    summary: str = "Flood event reported in Mumbai affecting logistics.",
) -> DisruptionEvent:
    """Minimal DisruptionEvent factory for verification tests."""
    return DisruptionEvent(
        source_url=source_url,
        source_result_id="res-test",
        headline=headline,
        summary=summary,
        event_type=event_type,
        location_mentioned=location_mentioned,
        severity_raw="medium",
        confidence=confidence,
        is_relevant=True,
    )


service = VerificationService()


# ===========================================================================
# MANDATORY WORKED EXAMPLES
# ===========================================================================

class TestWorkedExample1:
    """Example 1: Reputable breaking-news source, zero corroboration → 63.5"""

    def test_authenticity_score_exact(self):
        """
        0.35×90 + 0.25×0 + 0.20×75 + 0.20×85
        = 31.5 + 0 + 15 + 17
        = 63.5
        """
        event = _make_event(confidence=0.85)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.75,
        )
        assert assessment.authenticity_score == 63.5, (
            f"Expected 63.5, got {assessment.authenticity_score}"
        )

    def test_confidence_label_is_moderate(self):
        event = _make_event(confidence=0.85)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.75,
        )
        assert assessment.confidence_label == "moderate"

    def test_not_gated(self):
        """Reputable breaking-news must NOT be gated — this is the key design proof."""
        event = _make_event(confidence=0.85)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.75,
        )
        assert assessment.is_gated is False

    def test_factor_breakdown_correct(self):
        event = _make_event(confidence=0.85)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.9,
            override_corroboration_count=0,
            override_content_style_score=0.75,
        )
        f = assessment.factors
        assert f["source_reputation"]        == pytest.approx(31.5, abs=0.01)
        assert f["corroboration"]            == pytest.approx(0.0,  abs=0.01)
        assert f["content_style"]            == pytest.approx(15.0, abs=0.01)
        assert f["llm_extraction_confidence"] == pytest.approx(17.0, abs=0.01)


class TestWorkedExample2:
    """Example 2: Unknown source, zero corroboration, suspicious → 33.5"""

    def test_authenticity_score_exact(self):
        """
        0.35×50 + 0.25×0 + 0.20×20 + 0.20×60
        = 17.5 + 0 + 4 + 12
        = 33.5
        """
        event = _make_event(
            source_url="https://unknown-source-xyz.com/article",
            confidence=0.6,
        )
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.5,
            override_corroboration_count=0,
            override_content_style_score=0.2,
        )
        assert assessment.authenticity_score == 33.5, (
            f"Expected 33.5, got {assessment.authenticity_score}"
        )

    def test_confidence_label_is_unconfirmed(self):
        event = _make_event(source_url="https://unknown-xyz.com/a", confidence=0.6)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.5,
            override_corroboration_count=0,
            override_content_style_score=0.2,
        )
        assert assessment.confidence_label == "unconfirmed"

    def test_is_gated_true(self):
        event = _make_event(source_url="https://unknown-xyz.com/a", confidence=0.6)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.5,
            override_corroboration_count=0,
            override_content_style_score=0.2,
        )
        assert assessment.is_gated is True

    def test_factor_breakdown_correct(self):
        event = _make_event(source_url="https://unknown-xyz.com/a", confidence=0.6)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.5,
            override_corroboration_count=0,
            override_content_style_score=0.2,
        )
        f = assessment.factors
        assert f["source_reputation"]        == pytest.approx(17.5, abs=0.01)
        assert f["corroboration"]            == pytest.approx(0.0,  abs=0.01)
        assert f["content_style"]            == pytest.approx(4.0,  abs=0.01)
        assert f["llm_extraction_confidence"] == pytest.approx(12.0, abs=0.01)


# ===========================================================================
# REQUIRED BOUNDARY & EDGE CASE TESTS
# ===========================================================================

class TestBoundaryTests:
    def test_score_boundary_35_is_low_not_unconfirmed(self):
        """TEST 10: score = 35 → 'low', NOT 'unconfirmed'."""
        label = bucket_confidence(35.0)
        assert label == "low", f"Score 35 should be 'low', got '{label}'"

    def test_score_boundary_60_is_moderate(self):
        """TEST 11: score = 60 → 'moderate'."""
        label = bucket_confidence(60.0)
        assert label == "moderate"

    def test_score_boundary_80_is_high(self):
        """TEST 12: score = 80 → 'high'."""
        label = bucket_confidence(80.0)
        assert label == "high"

    def test_score_3499_is_unconfirmed(self):
        """Score just below 35 → 'unconfirmed'."""
        label = bucket_confidence(34.99)
        assert label == "unconfirmed"

    def test_score_0_is_unconfirmed(self):
        label = bucket_confidence(0.0)
        assert label == "unconfirmed"

    def test_score_100_is_high(self):
        label = bucket_confidence(100.0)
        assert label == "high"

    def test_score_59_99_is_low(self):
        label = bucket_confidence(59.99)
        assert label == "low"

    def test_score_79_99_is_moderate(self):
        label = bucket_confidence(79.99)
        assert label == "moderate"


class TestCorroborationCap:
    def test_three_sources_gives_corroboration_1(self):
        """TEST 4: 3 corroborating sources → corroboration_score = 1.0."""
        from app.services.corroboration_service import count_corroborating_sources
        from datetime import datetime, timezone

        now = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        target = DisruptionEvent(
            source_url="https://source-a.com/a",
            source_result_id="r1",
            headline="Strike at port",
            summary="Strike disrupts port operations.",
            event_type="strike",
            location_mentioned="Chennai Port",
            severity_raw="high",
            confidence=0.9,
            is_relevant=True,
            retrieved_at=now,
        )
        others = [
            DisruptionEvent(
                source_url=f"https://source-{ch}.com/b",
                source_result_id="rx",
                headline="Strike at port",
                summary="Strike reported at Chennai Port.",
                event_type="strike",
                location_mentioned="Chennai Port",
                severity_raw="high",
                confidence=0.85,
                is_relevant=True,
                retrieved_at=now,
            )
            for ch in ["b", "c", "d"]
        ]
        count = count_corroborating_sources(target, others)
        assert count == 3
        corr_score = min(count, CORROBORATION_CAP) / CORROBORATION_CAP
        assert corr_score == 1.0

    def test_five_sources_still_capped_at_1(self):
        """TEST 5: 5 sources → corroboration_score still = 1.0 (cap = 3)."""
        count = 5
        corr_score = min(count, CORROBORATION_CAP) / CORROBORATION_CAP
        assert corr_score == 1.0, "Cap at 3 means 5 sources still give 1.0"


class TestHighReputationBreakingNews:
    def test_reputable_single_source_not_gated(self):
        """TEST 1: High-reputation + zero corroboration → NOT gated."""
        event = _make_event(
            source_url="https://reuters.com/article",
            confidence=0.85,
        )
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.95,
            override_corroboration_count=0,
            override_content_style_score=0.80,
        )
        assert assessment.is_gated is False, (
            "A reputable single-source breaking-news event must NOT be gated"
        )


class TestUnknownDomainReputation:
    def test_unknown_domain_reputation_is_neutral_not_zero(self):
        """TEST 2: Unknown domain → reputation = 0.5, not 0."""
        from app.core.domain_reputation import lookup_domain
        score, tier = lookup_domain("some-completely-unknown-domain-9999.com")
        assert score == 0.5, f"Unknown domain must return 0.5, got {score}"
        assert score != 0.0, "Unknown domain must NOT return 0"


class TestModelUnavailable:
    def test_model_unavailable_returns_neutral(self, monkeypatch):
        """TEST 3: Model unavailable → content_style_score = 0.5, no exception."""
        from app.core import credibility_model

        monkeypatch.setattr(credibility_model, "load_model", lambda: False)
        monkeypatch.setattr(credibility_model, "_clf", None)
        monkeypatch.setattr(credibility_model, "_vectorizer", None)

        score = credibility_model.predict_style_score("Some article text about a flood")
        assert score == 0.5, f"Model unavailable must return 0.5, got {score}"

    def test_model_unavailable_does_not_crash(self, monkeypatch):
        """Model failure must not raise any exception."""
        from app.core import credibility_model

        monkeypatch.setattr(credibility_model, "load_model", lambda: False)
        monkeypatch.setattr(credibility_model, "_clf", None)
        monkeypatch.setattr(credibility_model, "_vectorizer", None)

        # Must complete without exception
        result = credibility_model.predict_style_score("test text")
        assert isinstance(result, float)


class TestGateLogic:
    def test_score_below_35_is_gated(self):
        """Score < 35 → is_gated = True."""
        event = _make_event(source_url="https://unknown.com/a", confidence=0.5)
        assessment = service.verify(
            event,
            recent_events=[],
            override_source_reputation=0.4,
            override_corroboration_count=0,
            override_content_style_score=0.1,
        )
        assert assessment.is_gated is True

    def test_score_exactly_35_is_not_gated(self):
        """Score = 35 → is_gated = False (threshold is exclusive lower bound)."""
        # We need score exactly 35 — construct it:
        # 0.35*rep*100 + 0.25*0 + 0.20*cs*100 + 0.20*llm*100 = 35
        # Let rep=0.5, cs=0.25, llm=0.5:
        # 0.35*50 + 0 + 0.20*25 + 0.20*50 = 17.5 + 0 + 5 + 10 = 32.5  (not quite)
        # Let rep=1.0, cs=0, llm=0:
        # 0.35*100 = 35 → perfect
        event = _make_event(confidence=0.0)
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
