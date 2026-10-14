"""Phase 3 Audit & Reliability Regression Test Suite.

Deterministic tests covering the findings and invariants audited in Phase 3:
1. Cross-source corroboration domain deduplication & syndication behavior.
2. Credibility bounds, gating threshold, and non-deletion in review queue.
3. Decoupling of credibility from event severity and business risk.
4. Weather corroboration safety (no false contradictory penalties).
5. Geospatial disambiguation without arbitrary tie-breaking.
6. Execution of the Phase 3 independent evaluation runner.
"""

from datetime import datetime, timezone, timedelta
import pytest
from unittest.mock import AsyncMock, patch

from tests.conftest import make_entity, make_event
from app.models.risk import RiskAssessment
from app.services.corroboration_service import count_corroborating_sources
from app.services.geo_matching_service import GeoMatchingService
from app.services.risk_service import RiskService
from app.services.verification_service import VerificationService
from app.services.weather_service import check_weather_corroboration
from evaluate_phase3 import run_independent_evaluation


# ---------------------------------------------------------------------------
# 1. Credibility & Corroboration Audits
# ---------------------------------------------------------------------------

def test_same_domain_articles_do_not_inflate_corroboration():
    """Verify that multiple articles from the same domain count as only 1 domain."""
    now = datetime.now(timezone.utc)
    target = make_event(
        source_url="https://reuters.com/news/article-primary",
        headline="Port strike in Rotterdam",
        summary="Dockworkers strike at Rotterdam port",
        event_type="strike",
        location_mentioned="Rotterdam",
    )
    target.published_at = now

    duplicate_reuters = [
        make_event(
            source_url="https://reuters.com/news/article-update-1",
            headline="Rotterdam port strike continues",
            summary="Updated coverage of Rotterdam strike",
            event_type="strike",
            location_mentioned="Rotterdam",
        ),
        make_event(
            source_url="https://reuters.com/world/europe/rotterdam-strike",
            headline="Rotterdam dock strike affects supply",
            summary="Third report from reuters on Rotterdam",
            event_type="strike",
            location_mentioned="Rotterdam",
        ),
    ]
    duplicate_reuters[0].published_at = now + timedelta(hours=2)
    duplicate_reuters[1].published_at = now + timedelta(hours=3)

    count = count_corroborating_sources(target, duplicate_reuters)
    # The target is reuters.com, all candidates are reuters.com -> 0 external corroborating domains
    assert count == 0, f"Expected 0 external domains, got {count}"


def test_syndicated_republication_across_domains_counted_per_domain():
    """Documents the current architectural limitation:

    Without text fingerprinting, syndicated wire copy published on different
    domains counts each domain once.
    """
    now = datetime.now(timezone.utc)
    target = make_event(
        source_url="https://reuters.com/news/article-original",
        headline="Port strike in Rotterdam",
        summary="Dockworkers strike at Rotterdam port",
        event_type="strike",
        location_mentioned="Rotterdam",
    )
    target.published_at = now

    syndicated = [
        make_event(
            source_url="https://yahoo.com/news/reuters-copy",
            headline="Port strike in Rotterdam",
            summary="Dockworkers strike at Rotterdam port (Reuters)",
            event_type="strike",
            location_mentioned="Rotterdam",
        ),
        make_event(
            source_url="https://msn.com/news/reuters-copy",
            headline="Port strike in Rotterdam",
            summary="Dockworkers strike at Rotterdam port (Reuters)",
            event_type="strike",
            location_mentioned="Rotterdam",
        ),
    ]
    syndicated[0].published_at = now + timedelta(hours=1)
    syndicated[1].published_at = now + timedelta(hours=1)

    count = count_corroborating_sources(target, syndicated)
    # Since yahoo.com and msn.com are distinct domains, each is counted.
    assert count == 2, f"Expected 2 unique domains, got {count}"


def test_credibility_score_bounds_and_gating_threshold():
    """Verify credibility remains in [0, 100] and gate threshold behavior."""
    verifier = VerificationService()

    # Highly disreputable source with no corroboration
    low_event = make_event(
        source_url="https://sketchy-tabloid.ru/rumors",
        headline="Factory vanished overnight",
        summary="Wild unsupported rumor",
        event_type="other",
        location_mentioned="Unknown",
        confidence=0.2,
    )
    cred_low = verifier.verify(low_event, [])
    assert 0.0 <= cred_low.authenticity_score <= 100.0
    assert cred_low.is_gated is True
    assert cred_low.confidence_label == "unconfirmed"

    # Prestigious source with corroboration
    high_event = make_event(
        source_url="https://reuters.com/business/flood",
        headline="Severe floods inundate port",
        summary="Verified flooding reports",
        event_type="flood",
        location_mentioned="Hamburg",
        confidence=0.9,
    )
    corr_event = make_event(
        source_url="https://bbc.com/news/hamburg-flood",
        headline="Hamburg port affected by heavy rains",
        summary="Flood waters rising in Hamburg",
        event_type="flood",
        location_mentioned="Hamburg",
    )
    cred_high = verifier.verify(high_event, [corr_event])
    assert 0.0 <= cred_high.authenticity_score <= 100.0
    assert cred_high.is_gated is False


def test_credibility_does_not_alter_event_severity():
    """Verify that credibility scoring does not mutate event.severity_raw."""
    verifier = VerificationService()
    event = make_event(
        source_url="https://reuters.com/news",
        headline="Minor transit delay",
        summary="Slight 10-minute delay",
        event_type="strike",
        location_mentioned="Berlin",
        severity_raw="low",
    )
    initial_severity = event.severity_raw
    cred = verifier.verify(event, [])
    assert event.severity_raw == initial_severity
    assert cred.authenticity_score > 50.0  # High domain reputation does not change event severity to 'high'


def test_high_domain_reputation_alone_does_not_cause_critical_business_risk():
    """Verify that reputable source reporting on low-criticality entity does not trigger high risk."""
    risk_svc = RiskService()
    entity = make_entity(
        id="ent-low",
        name="Ancillary Packaging Provider",
        type="supplier",
        location="Frankfurt, Germany",
        criticality="low",
        lead_time_days=2,
        alt_supplier=True,
    )
    event = make_event(
        source_url="https://reuters.com/top-news",
        headline="Brief power outage at regional warehouse",
        summary="Power restored within 15 minutes",
        event_type="other",
        location_mentioned="Frankfurt",
        severity_raw="low",
        confidence=0.95,
    )
    # High credibility (0.95)
    assessment: RiskAssessment = risk_svc.evaluate_risk(
        entity=entity,
        event=event,
        dependency_weight=0.1,  # minor leaf dependency
        credibility_score=0.95,
    )
    assert assessment.severity_score < 50.0
    assert assessment.risk_level in ("low", "medium")


# ---------------------------------------------------------------------------
# 2. Weather Corroboration Audits
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_weather_events_never_penalized_by_weather():
    """Non-weather event types yield 'not_checked' without credibility penalty."""
    event = make_event(
        source_url="https://reuters.com/labor/strike",
        headline="Dockworkers union declares strike",
        summary="Port workers walk out after contract talks fail",
        event_type="strike",
        location_mentioned="Antwerp",
    )
    entity = make_entity(
        id="ent-1",
        name="Antwerp Container Terminal",
        type="warehouse",
        location="Antwerp, Belgium",
        lat=51.2194,
        lon=4.4025,
    )
    signal = await check_weather_corroboration(event, entity)
    assert signal.classification == "not_checked"

    verifier = VerificationService()
    cred_with_signal = verifier.verify(event, [], weather_signal=signal)
    cred_without_signal = verifier.verify(event, [], weather_signal=None)
    # Score is unmodified
    assert cred_with_signal.authenticity_score == cred_without_signal.authenticity_score


@pytest.mark.asyncio
async def test_weather_api_failure_does_not_penalize_credibility():
    """When weather service returns None/error, classification is 'unavailable' with 0 penalty."""
    event = make_event(
        source_url="https://reuters.com/weather/flash-flood",
        headline="Flash flood submerges access road",
        summary="Water levels rise quickly",
        event_type="flood",
        location_mentioned="Valencia",
    )
    event.published_at = datetime.now(timezone.utc)

    entity = make_entity(
        id="ent-2",
        name="Valencia Distribution Hub",
        type="warehouse",
        location="Valencia, Spain",
        lat=39.4699,
        lon=-0.3763,
    )
    with patch(
        "app.services.weather_service.get_recent_weather",
        new_callable=AsyncMock,
        return_value=None,
    ):
        signal = await check_weather_corroboration(event, entity)
        assert signal.classification == "unavailable"

        verifier = VerificationService()
        cred_with_failure = verifier.verify(event, [], weather_signal=signal)
        cred_without_signal = verifier.verify(event, [], weather_signal=None)
        # Scores should be identical
        assert cred_with_failure.authenticity_score == cred_without_signal.authenticity_score


# ---------------------------------------------------------------------------
# 3. Geospatial Matching Audits
# ---------------------------------------------------------------------------

def test_same_name_city_ambiguity_not_arbitrarily_selected():
    """When two entities have similar match confidence in different regions,

    GeoMatchingService must mark LOCATION_AMBIGUOUS and not assign primary entity.
    """
    geo_svc = GeoMatchingService()
    event = make_event(
        source_url="https://localnews.com/incident",
        headline="Fire at Delta Industrial Park",
        summary="Smoke reported at Delta Industrial Park facility",
        event_type="closure",
        location_mentioned="Delta Industrial Park",
    )
    entities = [
        make_entity(
            id="ent-delta-surat",
            name="Delta Industrial Park",
            type="factory",
            location="Surat, Gujarat, India",
            lat=21.1702,
            lon=72.8311,
            city="Surat",
        ),
        make_entity(
            id="ent-delta-ahmedabad",
            name="Delta Industrial Park",
            type="factory",
            location="Ahmedabad, Gujarat, India",
            lat=23.0225,
            lon=72.5714,
            city="Ahmedabad",
        ),
    ]

    result = geo_svc.verify_and_match(event, entities)
    assert result.status == "LOCATION_AMBIGUOUS"
    assert result.primary_matched_entity_id is None
    assert result.ambiguity_reason is not None


# ---------------------------------------------------------------------------
# 4. Phase 3 Independent Evaluation Suite Integration
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_independent_evaluation_suite_runs_and_reports_methodology():
    """Verify that evaluate_phase3 executes completely and returns all required metric dimensions."""
    results = await run_independent_evaluation()
    assert results["evaluation_type"] == "independent"
    assert results["total_cases"] >= 60
    assert "synthetic_adversarial_scenarios" in results["label_methodology"]

    # Verify all metrics have value, numerator, and denominator
    for metric_name in [
        "active_disruption_precision",
        "active_disruption_recall",
        "resolved_event_false_positive_rate",
        "missed_active_disruption_rate",
        "weather_classification_accuracy",
        "geographic_match_accuracy",
        "human_review_rate",
        "review_routing_accuracy",
        "freshness_filter_accuracy",
    ]:
        m = results[metric_name]
        assert "value" in m
        assert "numerator" in m
        assert "denominator" in m
        assert 0.0 <= m["value"] <= 1.0
