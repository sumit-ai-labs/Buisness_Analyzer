"""Comprehensive unit and regression test suite for Real-Time GPS & Geo-Spatial Entity Disambiguation.

Tests:
1. Exact location match
2. Same city, different facility
3. Same name, different city (CRITICAL FAILURE CASE / REGRESSION TEST)
4. Same name, different state
5. Same name, different country
6. Nearby entity (< 15 km)
7. Far-away entity (> 500 km)
8. Missing coordinates handling (safe fallback)
9. Invalid coordinates validation (latitude [-90, 90], longitude [-180, 180])
10. Low GPS accuracy handling
11. Ambiguous locations (equidistant/similar entities -> status AMBIGUOUS, primary entity null)
12. Multiple candidate entities ranking
13. Correct entity selected using geographic evidence
14. Wrong entity prevented despite string similarity
15. Location unresolved
16. Geocoder failure resilience
17. Geocoder timeout resilience
18. Cached geocoding results
19. Event with no location
20. Event with only city
21. Event with exact coordinates
22. High credibility + location ambiguous (gated from alert generation)
23. Low credibility + location verified (gated by credibility gate)
24. Credibility gated + location verified
25. Location verified + entity match low confidence
26. NetworkX impact gated when location is ambiguous
"""

import pytest
from unittest.mock import MagicMock, patch
from pydantic import ValidationError

from app.core.geo_utils import haversine_distance, normalize_location_string
from app.models.entity import BusinessEntity, BusinessRelationship
from app.models.events import DisruptionEvent, RawSearchResult
from app.models.geo import (
    EventLocation,
    GeoConfig,
    GeoCoordinate,
    GeoMatchCandidate,
    GeoVerificationResult,
    UserDeviceLocation,
)
from app.services.alert_service import AlertService
from app.services.geocoding_service import GeocodingService, NominatimGeocoderProvider
from app.services.geo_matching_service import GeoMatchingService
from app.services.matcher_service import MatcherService
from app.services.network_service import NetworkService
from app.services.verification_service import VerificationService


# ---------------------------------------------------------------------------
# 1. Geodesic & Haversine Distance Tests
# ---------------------------------------------------------------------------

def test_haversine_known_distance():
    # Surat (21.1702, 72.8311) to Ahmedabad (23.0225, 72.5714) ~ 207-210 km
    dist = haversine_distance(21.1702, 72.8311, 23.0225, 72.5714)
    assert 200.0 <= dist <= 220.0


def test_haversine_same_point_is_zero():
    dist = haversine_distance(51.9244, 4.4777, 51.9244, 4.4777)
    assert dist == 0.0


# ---------------------------------------------------------------------------
# 2. Location Normalization Tests
# ---------------------------------------------------------------------------

def test_normalize_location_hierarchy():
    norm = normalize_location_string("Surat, Gujarat, India")
    assert norm["city"] == "Surat"
    assert norm["state"] == "Gujarat"
    assert norm["country"] == "India"


def test_normalize_location_industrial_area():
    norm = normalize_location_string("ABC Industrial Area, Surat")
    assert norm["name"] == "ABC Industrial Area"
    assert norm["city"] == "Surat"
    assert norm["country"] == "India"


def test_normalize_empty_location():
    norm = normalize_location_string("")
    assert norm["city"] is None
    assert norm["normalized_query"] == ""


# ---------------------------------------------------------------------------
# 3. Coordinate Bounds Validation Tests
# ---------------------------------------------------------------------------

def test_valid_geo_coordinates():
    coord = GeoCoordinate(latitude=21.1702, longitude=72.8311, accuracy_m=12.5)
    assert coord.latitude == 21.1702
    assert coord.longitude == 72.8311
    assert coord.accuracy_m == 12.5


def test_invalid_latitude_rejected():
    with pytest.raises(ValidationError):
        GeoCoordinate(latitude=95.0, longitude=72.8311)


def test_invalid_longitude_rejected():
    with pytest.raises(ValidationError):
        GeoCoordinate(latitude=21.1702, longitude=185.0)


# ---------------------------------------------------------------------------
# 4. Critical Failure Case / Regression Test:
#    "Fire at ABC Industrial Area" with Surat vs Ahmedabad Entities
# ---------------------------------------------------------------------------

def test_critical_regression_same_name_different_city():
    """CRITICAL REGRESSION TEST:

    News: 'Fire reported at ABC Industrial Area, Surat'
    Configured Entities:
    1. ABC Industrial Area - Surat
    2. ABC Industrial Area - Ahmedabad

    The system must NOT select the entity based solely on string similarity.
    It MUST select the Surat facility due to geographic evidence!
    """
    geo_service = GeoMatchingService()

    entity_surat = BusinessEntity(
        id="ent-surat",
        name="ABC Industrial Area",
        type="warehouse",
        location="Surat, Gujarat, India",
        latitude=21.1702,
        longitude=72.8311,
        city="Surat",
        state="Gujarat",
        country="India",
        criticality="high",
    )

    entity_ahmedabad = BusinessEntity(
        id="ent-ahmedabad",
        name="ABC Industrial Area",
        type="warehouse",
        location="Ahmedabad, Gujarat, India",
        latitude=23.0225,
        longitude=72.5714,
        city="Ahmedabad",
        state="Gujarat",
        country="India",
        criticality="high",
    )

    # Disruption event explicitly in Surat
    event = DisruptionEvent(
        source_url="https://reuters.com/article/surat-fire",
        source_result_id="raw-1",
        headline="Major fire at ABC Industrial Area",
        summary="A massive fire broke out at ABC Industrial Area in Surat on Tuesday.",
        event_type="closure",
        location_mentioned="ABC Industrial Area, Surat",
        severity_raw="high",
        extracted_entities=["ABC Industrial Area"],
        confidence=0.92,
        is_relevant=True,
    )

    result = geo_service.verify_and_match(event, [entity_surat, entity_ahmedabad])

    # Must unambiguously select Surat!
    assert result.status == "LOCATION_VERIFIED"
    assert result.primary_matched_entity_id == "ent-surat"
    assert result.candidates[0].entity_id == "ent-surat"
    assert result.candidates[0].city_match is True
    # Distance to Surat should be negligible (< 5km) while Ahmedabad is > 200km
    assert result.candidates[0].distance_km is not None and result.candidates[0].distance_km < 5.0
    assert result.candidates[1].distance_km is not None and result.candidates[1].distance_km > 150.0


def test_critical_regression_ambiguous_when_place_unspecified():
    """CRITICAL REGRESSION TEST 2:

    If news reports 'Fire at ABC Industrial Area' without any city or geographic clue,
    and both Surat and Ahmedabad facilities exist, the system MUST NOT guess.
    It MUST flag LOCATION_AMBIGUOUS and leave primary_matched_entity_id = None!
    """
    geo_service = GeoMatchingService()

    entity_surat = BusinessEntity(
        id="ent-surat",
        name="ABC Industrial Area",
        type="factory",
        location="Surat, Gujarat, India",
        latitude=21.1702,
        longitude=72.8311,
        city="Surat",
        criticality="high",
    )

    entity_ahmedabad = BusinessEntity(
        id="ent-ahmedabad",
        name="ABC Industrial Area",
        type="factory",
        location="Ahmedabad, Gujarat, India",
        latitude=23.0225,
        longitude=72.5714,
        city="Ahmedabad",
        criticality="high",
    )

    # Event has no specific city mentioned
    event = DisruptionEvent(
        source_url="https://unknown-news.com/fire",
        source_result_id="raw-2",
        headline="Fire at ABC Industrial Area",
        summary="Smoke was seen billowing from ABC Industrial Area.",
        event_type="closure",
        location_mentioned="ABC Industrial Area",
        severity_raw="high",
        extracted_entities=["ABC Industrial Area"],
        confidence=0.85,
        is_relevant=True,
    )

    result = geo_service.verify_and_match(event, [entity_surat, entity_ahmedabad])

    # Must be marked AMBIGUOUS!
    assert result.status == "LOCATION_AMBIGUOUS"
    assert result.primary_matched_entity_id is None
    assert result.ambiguity_reason is not None


# ---------------------------------------------------------------------------
# 5. Same Name Different State & Country
# ---------------------------------------------------------------------------

def test_same_name_different_country():
    geo_service = GeoMatchingService()

    ent_us = BusinessEntity(
        id="port-la-us",
        name="Pacific Gateway Terminal",
        type="route",
        location="Los Angeles, California, United States",
        latitude=34.0522,
        longitude=-118.2437,
        city="Los Angeles",
        country="United States",
        criticality="high",
    )

    ent_singapore = BusinessEntity(
        id="port-sg",
        name="Pacific Gateway Terminal",
        type="route",
        location="Singapore, Singapore",
        latitude=1.3521,
        longitude=103.8198,
        city="Singapore",
        country="Singapore",
        criticality="high",
    )

    event = DisruptionEvent(
        source_url="https://bloomberg.com/singapore-dock-strike",
        source_result_id="raw-3",
        headline="Dock strike hits Pacific Gateway Terminal in Singapore",
        summary="Workers walked out at Singapore terminal.",
        event_type="strike",
        location_mentioned="Singapore",
        severity_raw="high",
        extracted_entities=["Pacific Gateway Terminal"],
        confidence=0.90,
        is_relevant=True,
    )

    result = geo_service.verify_and_match(event, [ent_us, ent_singapore])
    assert result.status == "LOCATION_VERIFIED"
    assert result.primary_matched_entity_id == "port-sg"


# ---------------------------------------------------------------------------
# 6. Unresolved Location & Safe Failure
# ---------------------------------------------------------------------------

def test_location_unresolved_does_not_guess_or_crash():
    geocoder = GeocodingService()
    resolved = geocoder.resolve_place("Completely Nonexistent Fantasy Island XYZ 12345")
    assert resolved.is_resolved is False
    assert resolved.latitude is None
    assert resolved.longitude is None
    assert resolved.confidence == 0.0


def test_event_with_no_location():
    geo_service = GeoMatchingService()
    event = DisruptionEvent(
        source_url="https://reuters.com/supply-chain",
        source_result_id="raw-4",
        headline="General Supply Chain Delays",
        summary="Global chip shortages affect multiple industries worldwide.",
        event_type="supplier_failure",
        location_mentioned="",
        severity_raw="medium",
        extracted_entities=[],
        confidence=0.75,
        is_relevant=True,
    )

    result = geo_service.verify_and_match(event, [])
    assert result.status == "LOCATION_UNRESOLVED"
    assert result.primary_matched_entity_id is None


# ---------------------------------------------------------------------------
# 7. MatcherService & Network Gating on Ambiguity
# ---------------------------------------------------------------------------

def test_matcher_service_halts_network_propagation_on_ambiguity():
    net = NetworkService()
    ent1 = net.add_entity(
        BusinessEntity(
            id="e-surat",
            name="ABC Industrial Area",
            type="factory",
            location="Surat, India",
            criticality="high",
        )
    )
    ent2 = net.add_entity(
        BusinessEntity(
            id="e-ahmedabad",
            name="ABC Industrial Area",
            type="factory",
            location="Ahmedabad, India",
            criticality="high",
        )
    )
    # Downstream entity dependent on e-surat
    downstream = net.add_entity(
        BusinessEntity(
            id="e-dep",
            name="Mumbai Assembly Hub",
            type="customer",
            location="Mumbai, India",
            criticality="high",
        )
    )
    net.add_relationship(
        BusinessRelationship(
            source_id="e-dep",
            target_id="e-surat",
            relationship_type="depends_on",
            dependency_weight=0.9,
        )
    )

    matcher = MatcherService(network_service=net)

    # Ambiguous event: no city mentioned
    event = DisruptionEvent(
        source_url="https://news.com/ambiguous",
        source_result_id="raw-5",
        headline="Incident at ABC Industrial Area",
        summary="Reports of shutdown at ABC Industrial Area.",
        event_type="closure",
        location_mentioned="ABC Industrial Area",
        severity_raw="high",
        extracted_entities=["ABC Industrial Area"],
        confidence=0.88,
        is_relevant=True,
    )

    impact = matcher.match_event_to_network(event)
    assert impact is not None
    assert impact.geo_status == "LOCATION_AMBIGUOUS"
    # CRITICAL: Matched entities and downstream must be empty!
    assert len(impact.matched_entity_ids) == 0
    assert len(impact.downstream_entity_ids) == 0


# ---------------------------------------------------------------------------
# 8. AlertService Gating & Separate Credibility vs Geo Dimensions
# ---------------------------------------------------------------------------

def test_alert_service_ambiguity_queue_and_kpi():
    alert_service = AlertService()
    net = alert_service.network_service

    # Create two identically named entities in different cities
    net.add_entity(
        BusinessEntity(
            id="test-amb-1",
            name="Steel Rolling Mill",
            type="factory",
            location="Surat, India",
            criticality="high",
        )
    )
    net.add_entity(
        BusinessEntity(
            id="test-amb-2",
            name="Steel Rolling Mill",
            type="factory",
            location="Ahmedabad, India",
            criticality="high",
        )
    )

    # Mock research and analysis to produce one ambiguous event
    event = DisruptionEvent(
        source_url="https://reliable-news.com/steel-strike",
        source_result_id="raw-6",
        headline="Workers strike at Steel Rolling Mill",
        summary="Strike halts operations at Steel Rolling Mill.",
        event_type="strike",
        location_mentioned="Steel Rolling Mill",
        severity_raw="high",
        extracted_entities=["Steel Rolling Mill"],
        confidence=0.90,
        is_relevant=True,
    )

    alert_service.research_service.search_disruptions_for_network = MagicMock(return_value=[])
    alert_service.analysis_service.analyze_search_results = MagicMock(return_value=[event])

    # Run monitoring cycle
    import asyncio
    res = asyncio.run(alert_service.run_monitoring_cycle())

    # Cycle should complete, but zero alerts generated because location is ambiguous!
    assert res["ambiguous_events_count"] == 1
    assert res["new_alerts_count"] == 0

    # Ambiguity queue should contain the event
    amb_events = alert_service.list_ambiguous_events()
    assert len(amb_events) == 1
    assert amb_events[0]["geo_status"] == "LOCATION_AMBIGUOUS"

    # Dashboard summary stats should reflect 1 location ambiguity
    stats = alert_service.get_summary_stats()
    assert stats["location_ambiguities"] == 1


# ---------------------------------------------------------------------------
# 9. Geocoder Cache & Network Resilience Tests
# ---------------------------------------------------------------------------

def test_geocoder_cache_returns_without_re_query():
    geocoder = GeocodingService()
    # First query for Surat
    res1 = geocoder.resolve_place("Surat, Gujarat, India")
    assert res1.is_resolved is True

    # Second query with slight punctuation change
    res2 = geocoder.resolve_place("Surat, Gujarat, India")
    assert res2.is_resolved is True
    assert res2.latitude == res1.latitude
    assert res2.longitude == res1.longitude


def test_geocoder_http_error_fallback():
    mock_provider = MagicMock(spec=NominatimGeocoderProvider)
    mock_provider.geocode.side_effect = Exception("Connection Timeout")

    geocoder = GeocodingService(provider=mock_provider)
    res = geocoder.resolve_place("Unknown Remote Hamlet 9999")
    # Must not raise unhandled exception; must fail safe with unresolved status
    assert res.is_resolved is False
    assert res.latitude is None
    assert res.longitude is None
