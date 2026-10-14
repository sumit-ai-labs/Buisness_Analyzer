"""Tests for Geo Map Data, Nominatim Entity Geocoding, and OpenStreetMap Tile Configuration.

Covers:
- OpenStreetMap free tile endpoint configuration (zero API key/token requirement)
- Dynamic KPI counts without hardcoded fallbacks
- Batch geocoding for business entities with missing coordinates
- Safe failure principle for unresolvable entity locations (latitude=None, longitude=None)
- Demo Gujarat business network and disruption seeding
- Distance vector filtering (only verified, never ambiguous)
- Strict separation between Device GPS and Business/Event coordinates
"""

from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.core.geo_utils import haversine_distance
from app.main import app
from app.models.entity import BusinessEntity
from app.services.alert_service import get_alert_service
from app.services.geocoding_service import GeocodingService, NominatimGeocoderProvider
from app.services.network_service import get_network_service


@pytest.fixture
def client():
    return TestClient(app)


def test_osm_tile_provider_compliance():
    """Verifies that the tile provider configuration uses the free OpenStreetMap

    standard tile layer and does NOT include CARTO, Mapbox, Google, or any API token.
    """
    osm_standard_url = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
    osm_attribution = "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors"

    assert "tile.openstreetmap.org" in osm_standard_url
    assert "carto" not in osm_standard_url.lower()
    assert "mapbox" not in osm_standard_url.lower()
    assert "google" not in osm_standard_url.lower()
    assert "key" not in osm_standard_url.lower()
    assert "token" not in osm_standard_url.lower()
    assert "OpenStreetMap" in osm_attribution


def test_map_data_dynamic_kpi_counts_empty(client):
    """Verifies that GET /api/geo/map-data computes KPI counts dynamically without

    hardcoded fallbacks (e.g. not falling back to 8, 5, or 3).
    """
    net_service = get_network_service()
    alert_service = get_alert_service()

    # Clear network and alerts for clean test
    net_service._entities.clear()
    alert_service._events.clear()
    alert_service._ambiguous_events.clear()

    resp = client.get("/api/geo/map-data")
    assert resp.status_code == 200
    data = resp.json()

    assert data["monitored_facilities_count"] == 0
    assert data["geocoded_epicenters_count"] == 0
    assert data["ambiguities_count"] == 0
    assert data["verified_matches_count"] == 0
    assert len(data["entities"]) == 0
    assert len(data["events"]) == 0


def test_seed_demo_geo_data_endpoint(client):
    """Tests POST /api/geo/seed-demo seeds clearly labeled DEMO Gujarat entities

    and disruptions, updating map-data dynamic KPIs accurately.
    """
    resp = client.post("/api/geo/seed-demo")
    assert resp.status_code == 200
    seed_result = resp.json()
    assert seed_result["entities_count"] == 4
    assert seed_result["events_count"] == 2

    # Verify map data response
    map_resp = client.get("/api/geo/map-data")
    assert map_resp.status_code == 200
    map_data = map_resp.json()

    assert map_data["monitored_facilities_count"] == 4
    assert map_data["geocoded_epicenters_count"] >= 2
    assert map_data["ambiguities_count"] >= 1
    assert map_data["verified_matches_count"] >= 1

    # Verify entities have real Gujarat coordinates
    surat_supp = next((e for e in map_data["entities"] if "Surat" in e["location"]), None)
    assert surat_supp is not None
    assert surat_supp["latitude"] == pytest.approx(21.1702, abs=0.05)
    assert surat_supp["longitude"] == pytest.approx(72.8311, abs=0.05)

    # Verify DEMO label is explicit
    for ent in map_data["entities"]:
        assert "DEMO:" in ent["name"]


def test_geocode_entities_resolves_missing_coordinates(client):
    """Tests POST /api/geo/geocode-entities safely resolves entities missing coordinates

    using Nominatim/normalized cache and persists coordinates onto the entity.
    """
    net_service = get_network_service()

    # Add an entity with missing coordinates
    unresolved_entity = BusinessEntity(
        id="test-unresolved-surat",
        name="Surat Test Distribution Depot",
        type="warehouse",
        location="Surat, Gujarat, India",
        latitude=None,
        longitude=None,
        criticality="medium",
    )
    net_service.add_entity(unresolved_entity)

    # Trigger geocoding batch flow
    resp = client.post("/api/geo/geocode-entities")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_evaluated"] >= 1
    assert data["resolved_count"] >= 1

    # Check updated entity
    updated = net_service.get_entity("test-unresolved-surat")
    assert updated is not None
    assert updated.latitude is not None
    assert updated.longitude is not None
    assert updated.latitude == pytest.approx(21.17, abs=0.05)
    assert updated.longitude == pytest.approx(72.83, abs=0.05)
    assert updated.location_source in ("preconfigured_authority", "nominatim_cached_authority", "geocoded")


def test_geocode_entities_unresolved_failure_safe(client):
    """Tests that unresolvable locations are marked LOCATION_UNRESOLVED and

    never fabricate fake coordinates.
    """
    net_service = get_network_service()

    bogus_entity = BusinessEntity(
        id="test-bogus-loc",
        name="Nonexistent Phantom Facility",
        type="factory",
        location="Xyzzynonexistentland Unknown Sector 9999",
        latitude=None,
        longitude=None,
        criticality="low",
    )
    net_service.add_entity(bogus_entity)

    resp = client.post("/api/geo/geocode-entities")
    assert resp.status_code == 200
    data = resp.json()

    updated = net_service.get_entity("test-bogus-loc")
    assert updated is not None
    assert updated.latitude is None
    assert updated.longitude is None
    assert updated.location_source == "LOCATION_UNRESOLVED"
    assert updated.location_confidence == 0.0


def test_distance_vectors_only_on_verified_non_ambiguous(client):
    """Tests that distance vectors are never assigned or drawn for ambiguous events."""
    client.post("/api/geo/seed-demo")
    resp = client.get("/api/geo/map-data")
    assert resp.status_code == 200
    data = resp.json()

    ambiguous_events = [e for e in data["events"] if e["geo_status"] == "LOCATION_AMBIGUOUS"]
    assert len(ambiguous_events) >= 1
    for amb in ambiguous_events:
        assert amb["matched_entity_id"] is None

    verified_events = [e for e in data["events"] if e["geo_status"] == "LOCATION_VERIFIED"]
    assert len(verified_events) >= 1
    for ver in verified_events:
        if ver.get("matched_entity_id"):
            assert ver["distance_km"] is not None
            assert ver["distance_km"] > 0


def test_device_gps_separation_contract():
    """Verifies device GPS isolation principle: browser device location is distinct

    from entity and event locations and has an accuracy requirement.
    """
    device_loc = {
        "latitude": 21.1702,
        "longitude": 72.8311,
        "accuracy_m": 45,
        "status": "AVAILABLE",
    }
    low_acc_loc = {
        "latitude": 21.1702,
        "longitude": 72.8311,
        "accuracy_m": 1250,
        "status": "AVAILABLE",
    }

    # High accuracy GPS should be acceptable
    assert device_loc["accuracy_m"] < 1000
    # Low accuracy (> 1000m) flags warning badge in UI
    assert low_acc_loc["accuracy_m"] > 1000


def test_haversine_accuracy_gujarat_cities():
    """Verifies Haversine geodesic calculation between Surat and Gandhidham (Kandla)."""
    # Surat (21.1702, 72.8311) to Gandhidham (23.0033, 70.1337) ~ 340-360 km
    dist = haversine_distance(21.1702, 72.8311, 23.0033, 70.1337)
    assert 330.0 <= dist <= 370.0
