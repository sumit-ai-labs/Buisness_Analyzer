"""Geographic Intelligence API endpoints.

Exposes endpoints for:
- Retrieving event geographic verification and disambiguation details.
- Querying candidate entity matches, distances, and evidence breakdown.
- Inspecting the location ambiguity review queue.
- Geocoding arbitrary location strings (with caching and error safety).
- Map data endpoint combining entities and disruption events for geospatial visualization.
- Geo configuration tuning (max distance, ambiguity threshold, min confidence).
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.security import TokenData, get_current_user
from app.core.geo_utils import KNOWN_CITY_HIERARCHY, normalize_location_string
from app.models.entity import BusinessEntity, BusinessRelationship, EntityMetadata
from app.models.events import DisruptionEvent
from app.models.geo import EventLocation, GeoConfig, GeoMatchCandidate, GeoVerificationResult
from app.services.alert_service import AlertService, get_alert_service
from app.services.geocoding_service import GeocodingService, get_geocoding_service
from app.services.geo_matching_service import GeoMatchingService, get_geo_matching_service
from app.services.network_service import NetworkService, get_network_service

router = APIRouter(prefix="/geo", tags=["Geographic Intelligence"])


class ResolveLocationRequest(BaseModel):
    query: str


class GeocodeEntitiesResponse(BaseModel):
    total_evaluated: int
    resolved_count: int
    unresolved_count: int
    message: str
    results: List[Dict[str, Any]] = []


class MapDataResponse(BaseModel):
    entities: List[Dict[str, Any]]
    events: List[Dict[str, Any]]
    ambiguities_count: int
    monitored_facilities_count: int = 0
    geocoded_epicenters_count: int = 0
    verified_matches_count: int = 0


@router.get("/events/{event_id}", response_model=GeoVerificationResult)
def get_event_geo_verification(
    event_id: str,
    alert_service: AlertService = Depends(get_alert_service),
    geo_service: GeoMatchingService = Depends(get_geo_matching_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns the full geographic verification and candidate match breakdown for an event."""
    geo_res = alert_service.get_geo_verification_for_event(event_id)
    if geo_res:
        return geo_res

    # If not yet stored in alert_service, check if event exists and run on-demand
    event = (
        alert_service._events.get(event_id)
        or alert_service._unconfirmed_events.get(event_id)
        or (alert_service._ambiguous_events.get(event_id)[0] if event_id in alert_service._ambiguous_events else None)
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with ID '{event_id}' not found.",
        )

    res = geo_service.verify_and_match(event)
    return res


@router.get("/events/{event_id}/matches")
def get_event_geo_matches(
    event_id: str,
    alert_service: AlertService = Depends(get_alert_service),
    geo_service: GeoMatchingService = Depends(get_geo_matching_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns all evaluated candidate business entities, distances, and match scores for an event."""
    geo_res = alert_service.get_geo_verification_for_event(event_id)
    if not geo_res:
        event = (
            alert_service._events.get(event_id)
            or alert_service._unconfirmed_events.get(event_id)
            or (alert_service._ambiguous_events.get(event_id)[0] if event_id in alert_service._ambiguous_events else None)
        )
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID '{event_id}' not found.",
            )
        geo_res = geo_service.verify_and_match(event)

    return {
        "event_id": event_id,
        "event_location": geo_res.event_location.model_dump(),
        "status": geo_res.status,
        "location_confidence": geo_res.location_confidence,
        "entity_match_confidence": geo_res.entity_match_confidence,
        "primary_matched_entity_id": geo_res.primary_matched_entity_id,
        "primary_matched_entity_name": geo_res.primary_matched_entity_name,
        "distance_km": geo_res.distance_km,
        "candidates": [c.model_dump() for c in geo_res.candidates],
        "ambiguity_reason": geo_res.ambiguity_reason,
    }


@router.get("/ambiguities")
def list_location_ambiguities(
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns disruption events flagged as LOCATION_AMBIGUOUS awaiting operator review."""
    return alert_service.list_ambiguous_events()


@router.post("/resolve", response_model=EventLocation)
def resolve_location(
    req: ResolveLocationRequest,
    geocoder: GeocodingService = Depends(get_geocoding_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Resolves an arbitrary location string into canonical coordinates and administrative hierarchy."""
    return geocoder.resolve_place(req.query)


@router.get("/map-data", response_model=MapDataResponse)
def get_map_data(
    network_service: NetworkService = Depends(get_network_service),
    alert_service: AlertService = Depends(get_alert_service),
    geocoder: GeocodingService = Depends(get_geocoding_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Aggregates all business entities and active disruption events with canonical GPS coordinates

    for rendering the enterprise geographic map. Dynamically computes all KPI counts.
    """
    entities = network_service.list_entities()
    entity_items = []
    for ent in entities:
        lat = ent.latitude
        lon = ent.longitude
        city = ent.city
        country = ent.country

        # Fast offline cache check for known cities if coordinates not yet stored
        if lat is None or lon is None:
            query = ent.location or ent.address or ent.city or ""
            norm = normalize_location_string(query)
            city_key = (norm.get("city") or "").lower()
            if city_key in KNOWN_CITY_HIERARCHY:
                info = KNOWN_CITY_HIERARCHY[city_key]
                lat = info["lat"]
                lon = info["lon"]
                city = city or info["city"]
                country = country or info.get("country")

        entity_items.append({
            "id": ent.id,
            "name": ent.name,
            "type": ent.type,
            "location": ent.location,
            "city": city,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "criticality": ent.criticality,
            "status": ent.status,
            "location_source": ent.location_source,
            "location_confidence": ent.location_confidence,
        })

    event_items = []
    # Include both active verified events and ambiguous events
    for evt in alert_service.list_events():
        geo = alert_service.get_geo_verification_for_event(evt.id)
        cred = alert_service.get_credibility_assessment(evt.credibility_assessment_id) if evt.credibility_assessment_id else None
        event_items.append({
            "id": evt.id,
            "headline": evt.headline,
            "event_type": evt.event_type,
            "severity": evt.severity_raw,
            "location_mentioned": evt.location_mentioned,
            "latitude": evt.event_latitude or (geo.event_location.latitude if geo else None),
            "longitude": evt.event_longitude or (geo.event_location.longitude if geo else None),
            "city": evt.event_city or (geo.event_location.city if geo else None),
            "location_confidence": geo.location_confidence if geo else 0.0,
            "entity_match_confidence": geo.entity_match_confidence if geo else 0.0,
            "authenticity_score": cred.authenticity_score if cred else 65.0,
            "geo_status": geo.status if geo else "LOCATION_VERIFIED",
            "matched_entity_id": geo.primary_matched_entity_id if geo else None,
            "distance_km": geo.distance_km if geo else None,
        })

    for evt_id, (evt, geo) in alert_service._ambiguous_events.items():
        cred = alert_service.get_credibility_assessment(evt.credibility_assessment_id) if evt.credibility_assessment_id else None
        event_items.append({
            "id": evt.id,
            "headline": evt.headline,
            "event_type": evt.event_type,
            "severity": evt.severity_raw,
            "location_mentioned": evt.location_mentioned,
            "latitude": evt.event_latitude or geo.event_location.latitude,
            "longitude": evt.event_longitude or geo.event_location.longitude,
            "city": evt.event_city or geo.event_location.city,
            "location_confidence": geo.location_confidence,
            "entity_match_confidence": geo.entity_match_confidence,
            "authenticity_score": cred.authenticity_score if cred else 65.0,
            "geo_status": "LOCATION_AMBIGUOUS",
            "matched_entity_id": None,
            "distance_km": geo.distance_km,
            "ambiguity_reason": geo.ambiguity_reason,
            "candidates": [c.model_dump() for c in geo.candidates],
        })

    # Dynamically compute KPI counts
    monitored_facilities_count = sum(
        1 for e in entity_items if e.get("latitude") is not None and e.get("longitude") is not None
    )
    geocoded_epicenters_count = sum(
        1 for ev in event_items if ev.get("latitude") is not None and ev.get("longitude") is not None
    )
    ambiguities_count = len(alert_service._ambiguous_events) + sum(
        1 for ev in event_items if ev.get("geo_status") == "LOCATION_AMBIGUOUS" and ev["id"] not in alert_service._ambiguous_events
    )
    verified_matches_count = sum(
        1 for ev in event_items if ev.get("geo_status") == "LOCATION_VERIFIED" and ev.get("matched_entity_id") is not None
    )

    return MapDataResponse(
        entities=entity_items,
        events=event_items,
        ambiguities_count=ambiguities_count,
        monitored_facilities_count=monitored_facilities_count,
        geocoded_epicenters_count=geocoded_epicenters_count,
        verified_matches_count=verified_matches_count,
    )


@router.post("/geocode-entities", response_model=GeocodeEntitiesResponse)
def geocode_entities(
    network_service: NetworkService = Depends(get_network_service),
    geocoder: GeocodingService = Depends(get_geocoding_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Finds business entities missing latitude/longitude coordinates and attempts

    to safely resolve their geographic coordinates via cached hierarchy or rate-limited Nominatim.
    Updates the business entity records directly in network_service.
    """
    entities = network_service.list_entities()
    missing_entities = [e for e in entities if e.latitude is None or e.longitude is None]

    total_evaluated = len(missing_entities)
    resolved_count = 0
    unresolved_count = 0
    results = []

    for ent in missing_entities:
        query = ent.location or ent.address or ent.city or ""
        resolved = geocoder.resolve_place(query)

        if resolved.is_resolved and resolved.latitude is not None and resolved.longitude is not None:
            patch = {
                "latitude": resolved.latitude,
                "longitude": resolved.longitude,
                "city": ent.city or resolved.city,
                "district": ent.district or resolved.district,
                "state": ent.state or resolved.state,
                "country": ent.country or resolved.country,
                "postal_code": ent.postal_code or resolved.postal_code,
                "location_source": resolved.source or "geocoded",
                "location_confidence": resolved.confidence,
            }
            network_service.update_entity(ent.id, patch)
            resolved_count += 1
            results.append({
                "entity_id": ent.id,
                "name": ent.name,
                "status": "RESOLVED",
                "latitude": resolved.latitude,
                "longitude": resolved.longitude,
                "location_source": resolved.source,
            })
        else:
            patch = {
                "location_source": "LOCATION_UNRESOLVED",
                "location_confidence": 0.0,
            }
            network_service.update_entity(ent.id, patch)
            unresolved_count += 1
            results.append({
                "entity_id": ent.id,
                "name": ent.name,
                "status": "LOCATION_UNRESOLVED",
                "message": "Location could not be resolved",
            })

    if total_evaluated == 0:
        msg = "All configured business entities already have verified coordinates."
    elif unresolved_count > 0:
        msg = f"{resolved_count} resolved · {unresolved_count} require review"
    else:
        msg = f"{resolved_count} locations resolved"

    return GeocodeEntitiesResponse(
        total_evaluated=total_evaluated,
        resolved_count=resolved_count,
        unresolved_count=unresolved_count,
        message=msg,
        results=results,
    )


@router.post("/seed-demo")
def seed_demo_geo_data(
    network_service: NetworkService = Depends(get_network_service),
    alert_service: AlertService = Depends(get_alert_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Seeds a set of explicitly labeled demo business entities in Gujarat/India with real public

    coordinates, dependency relationships, and demo disruption events to populate the map.
    """
    demo_entities = [
        BusinessEntity(
            id="demo-supp-surat",
            name="DEMO: Western India Component Supplier",
            type="supplier",
            location="Surat, Gujarat, India",
            city="Surat",
            state="Gujarat",
            country="India",
            latitude=21.1702,
            longitude=72.8311,
            criticality="high",
            location_source="demo_verified",
            location_confidence=0.98,
            metadata=EntityMetadata(lead_time_days=14, alternative_supplier_available=False),
        ),
        BusinessEntity(
            id="demo-fact-ahmedabad",
            name="DEMO: Gujarat Assembly Gigafactory",
            type="factory",
            location="Ahmedabad, Gujarat, India",
            city="Ahmedabad",
            state="Gujarat",
            country="India",
            latitude=23.0225,
            longitude=72.5714,
            criticality="high",
            location_source="demo_verified",
            location_confidence=0.98,
            metadata=EntityMetadata(lead_time_days=21, alternative_supplier_available=True),
        ),
        BusinessEntity(
            id="demo-ware-surat",
            name="DEMO: Central Logistics Warehouse",
            type="warehouse",
            location="Surat, Gujarat, India",
            city="Surat",
            state="Gujarat",
            country="India",
            latitude=21.1959,
            longitude=72.8302,
            criticality="medium",
            location_source="demo_verified",
            location_confidence=0.95,
            metadata=EntityMetadata(lead_time_days=7, alternative_supplier_available=True),
        ),
        BusinessEntity(
            id="demo-port-kandla",
            name="DEMO: Kandla Export Terminal Port",
            type="route",
            location="Gandhidham, Gujarat, India",
            city="Gandhidham",
            state="Gujarat",
            country="India",
            latitude=23.0033,
            longitude=70.1337,
            criticality="medium",
            location_source="demo_verified",
            location_confidence=0.95,
            metadata=EntityMetadata(lead_time_days=10, alternative_supplier_available=False),
        ),
    ]

    for ent in demo_entities:
        network_service.add_entity(ent)

    demo_rels = [
        BusinessRelationship(
            id="demo-rel-1",
            source_id="demo-fact-ahmedabad",
            target_id="demo-supp-surat",
            relationship_type="supplies",
            dependency_weight=0.85,
        ),
        BusinessRelationship(
            id="demo-rel-2",
            source_id="demo-ware-surat",
            target_id="demo-fact-ahmedabad",
            relationship_type="stores_at",
            dependency_weight=0.70,
        ),
        BusinessRelationship(
            id="demo-rel-3",
            source_id="demo-ware-surat",
            target_id="demo-port-kandla",
            relationship_type="ships_to",
            dependency_weight=0.60,
        ),
    ]
    for rel in demo_rels:
        try:
            network_service.add_relationship(rel)
        except Exception:
            pass

    verified_event = DisruptionEvent(
        id="demo-evt-verified",
        source_url="https://demo-logistics-news.example.com/kandla-strike",
        source_result_id="demo-res-1",
        headline="DEMO: Port Logistics Action at Kandla Terminal",
        summary="A temporary terminal slowdown was announced at Kandla port facilities.",
        event_type="strike",
        location_mentioned="Gandhidham, Gujarat, India",
        severity_raw="medium",
        extracted_entities=["Kandla Export Terminal Port"],
        confidence=0.94,
        is_relevant=True,
        event_latitude=23.0150,
        event_longitude=70.1410,
        event_city="Gandhidham",
    )
    verified_geo = GeoVerificationResult(
        id="demo-geo-verified",
        event_id="demo-evt-verified",
        event_location=EventLocation(
            raw_text="Gandhidham, Gujarat, India",
            city="Gandhidham",
            state="Gujarat",
            country="India",
            latitude=23.0150,
            longitude=70.1410,
            confidence=0.95,
            source="demo_verified",
            is_resolved=True,
        ),
        status="LOCATION_VERIFIED",
        location_confidence=95.0,
        entity_match_confidence=92.0,
        primary_matched_entity_id="demo-port-kandla",
        primary_matched_entity_name="DEMO: Kandla Export Terminal Port",
        distance_km=1.52,
        candidates=[
            GeoMatchCandidate(
                entity_id="demo-port-kandla",
                entity_name="DEMO: Kandla Export Terminal Port",
                entity_type="route",
                entity_location="Gandhidham, Gujarat, India",
                entity_latitude=23.0033,
                entity_longitude=70.1337,
                distance_km=1.52,
                city_match=True,
                state_match=True,
                country_match=True,
                name_similarity=0.88,
                geo_confidence=0.94,
                status="MATCH",
                match_reasons=["Proximity < 5km", "City match", "State match"],
            )
        ],
    )
    alert_service._events[verified_event.id] = verified_event
    alert_service._geo_verifications[verified_geo.id] = verified_geo
    alert_service._event_geo_map[verified_event.id] = verified_geo.id

    ambiguous_event = DisruptionEvent(
        id="demo-evt-ambiguous",
        source_url="https://demo-news.example.com/industrial-fire",
        source_result_id="demo-res-2",
        headline="DEMO: Fire reported at Industrial Area Warehouse",
        summary="Emergency units dispatched following reports of fire at Industrial Area Warehouse.",
        event_type="closure",
        location_mentioned="Industrial Area",
        severity_raw="high",
        extracted_entities=["Industrial Area Warehouse"],
        confidence=0.86,
        is_relevant=True,
        event_latitude=21.1702,
        event_longitude=72.8311,
        event_city="Surat",
    )
    ambiguous_geo = GeoVerificationResult(
        id="demo-geo-ambiguous",
        event_id="demo-evt-ambiguous",
        event_location=EventLocation(
            raw_text="Industrial Area",
            city=None,
            state=None,
            country=None,
            latitude=21.1702,
            longitude=72.8311,
            confidence=0.45,
            source="demo_unspecified",
            is_resolved=False,
        ),
        status="LOCATION_AMBIGUOUS",
        location_confidence=45.0,
        entity_match_confidence=50.0,
        primary_matched_entity_id=None,
        primary_matched_entity_name=None,
        distance_km=None,
        ambiguity_reason="Multiple facilities exist with matching names and no definitive city specified. NetworkX traversal gated.",
        candidates=[
            GeoMatchCandidate(
                entity_id="demo-ware-surat",
                entity_name="DEMO: Central Logistics Warehouse",
                entity_type="warehouse",
                entity_location="Surat, Gujarat, India",
                entity_latitude=21.1959,
                entity_longitude=72.8302,
                distance_km=2.86,
                city_match=False,
                state_match=False,
                country_match=False,
                name_similarity=0.72,
                geo_confidence=0.55,
                status="AMBIGUOUS",
                match_reasons=["Name similarity", "Surat proximity"],
            ),
            GeoMatchCandidate(
                entity_id="demo-fact-ahmedabad",
                entity_name="DEMO: Gujarat Assembly Gigafactory",
                entity_type="factory",
                entity_location="Ahmedabad, Gujarat, India",
                entity_latitude=23.0225,
                entity_longitude=72.5714,
                distance_km=208.5,
                city_match=False,
                state_match=False,
                country_match=False,
                name_similarity=0.45,
                geo_confidence=0.35,
                status="REJECTED",
                match_reasons=["Distance > 200km"],
            ),
        ],
    )
    alert_service._ambiguous_events[ambiguous_event.id] = (ambiguous_event, ambiguous_geo)

    return {
        "message": "Demo Gujarat business network and sample disruptions seeded successfully.",
        "entities_count": len(demo_entities),
        "events_count": 2,
    }


@router.get("/config", response_model=GeoConfig)
def get_geo_config(
    geo_service: GeoMatchingService = Depends(get_geo_matching_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Returns current geographic matching & disambiguation settings."""
    return geo_service.config


@router.put("/config", response_model=GeoConfig)
def update_geo_config(
    patch: GeoConfig,
    geo_service: GeoMatchingService = Depends(get_geo_matching_service),
    current_user: TokenData = Depends(get_current_user),
):
    """Updates geographic matching settings (max distance, ambiguity threshold, etc.)."""
    geo_service.config = patch
    return geo_service.config
