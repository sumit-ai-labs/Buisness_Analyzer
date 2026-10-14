"""Geographic Entity Matching & Disambiguation Engine.

Responsibilities:
- Compare event location with configured business entities.
- Calculate geographic distance (Haversine).
- Evaluate administrative hierarchy matches (city, state, country).
- Evaluate name/place-string lexical similarity (RapidFuzz).
- Calculate multi-factor explainable geo-confidence.
- Detect ambiguous entities (multiple close matches) without guessing.
- Produce GeoVerificationResult for integration into pipeline.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple
from rapidfuzz import fuzz

from app.core.geo_utils import haversine_distance, normalize_location_string
from app.models.entity import BusinessEntity
from app.models.events import DisruptionEvent
from app.models.geo import (
    EventLocation,
    GeoConfig,
    GeoMatchCandidate,
    GeoVerificationResult,
)
from app.services.geocoding_service import GeocodingService, get_geocoding_service
from app.services.network_service import NetworkService, get_network_service

logger = logging.getLogger("business_disruption")


class GeoMatchingService:
    """Enterprise Geo-Matching and Disambiguation Service."""

    def __init__(
        self,
        geocoding_service: Optional[GeocodingService] = None,
        network_service: Optional[NetworkService] = None,
        config: Optional[GeoConfig] = None,
    ):
        self.geocoding_service = geocoding_service or get_geocoding_service()
        self.network_service = network_service or get_network_service()
        self.config = config or GeoConfig()

    def calculate_distance_factor(self, distance_km: Optional[float]) -> float:
        """Converts Haversine distance into a 0.0 to 1.0 proximity score."""
        if distance_km is None:
            return 0.40  # Neutral proximity score when coordinates are unavailable

        if distance_km <= 15.0:
            return 1.0
        elif distance_km <= 35.0:
            return 0.90
        elif distance_km <= 75.0:
            return 0.75
        elif distance_km <= 150.0:
            return 0.50
        elif distance_km <= 300.0:
            return 0.25
        elif distance_km <= 600.0:
            return 0.05
        else:
            return 0.0

    def evaluate_candidate(
        self, event_loc: EventLocation, event: DisruptionEvent, entity: BusinessEntity
    ) -> GeoMatchCandidate:
        """Evaluates geographic and textual correspondence between an event and an entity."""
        reasons: List[str] = []

        # 1. Normalize entity location if not already done
        ent_city = entity.city
        ent_state = entity.state
        ent_country = entity.country
        ent_lat = entity.latitude
        ent_lon = entity.longitude

        if not ent_city or not ent_country:
            norm_ent = normalize_location_string(entity.location)
            ent_city = ent_city or norm_ent.get("city")
            ent_state = ent_state or norm_ent.get("state")
            ent_country = ent_country or norm_ent.get("country")

        # Resolve entity coordinates if missing and configured location exists
        if ent_lat is None or ent_lon is None:
            resolved_ent = self.geocoding_service.resolve_place(entity.location)
            if resolved_ent.is_resolved:
                ent_lat = resolved_ent.latitude
                ent_lon = resolved_ent.longitude
                ent_city = ent_city or resolved_ent.city
                ent_state = ent_state or resolved_ent.state
                ent_country = ent_country or resolved_ent.country

        # 2. Administrative Region Matching
        city_match = False
        if event_loc.city and ent_city:
            city_match = (
                event_loc.city.strip().lower() == ent_city.strip().lower()
                or fuzz.ratio(event_loc.city.lower(), ent_city.lower()) >= 85
            )
            if city_match:
                reasons.append(f"City match verified ({ent_city})")

        state_match = False
        if event_loc.state and ent_state:
            state_match = (
                event_loc.state.strip().lower() == ent_state.strip().lower()
                or fuzz.ratio(event_loc.state.lower(), ent_state.lower()) >= 85
            )
            if state_match:
                reasons.append(f"State/region match verified ({ent_state})")

        country_match = False
        if event_loc.country and ent_country:
            country_match = (
                event_loc.country.strip().lower() == ent_country.strip().lower()
                or fuzz.ratio(event_loc.country.lower(), ent_country.lower()) >= 85
            )
            if country_match:
                reasons.append(f"Country match verified ({ent_country})")

        # 3. Geo-Distance Calculation
        distance_km: Optional[float] = None
        if (
            event_loc.latitude is not None
            and event_loc.longitude is not None
            and ent_lat is not None
            and ent_lon is not None
        ):
            distance_km = haversine_distance(
                event_loc.latitude, event_loc.longitude, ent_lat, ent_lon
            )
            reasons.append(f"Distance: {distance_km:.1f} km from event epicenter")

        distance_score = self.calculate_distance_factor(distance_km)

        # 4. Place & Entity Name Similarity
        # Compare event headline, location_mentioned, extracted_entities with entity name and location
        name_scores = []
        if event_loc.name:
            name_scores.append(fuzz.partial_ratio(event_loc.name.lower(), entity.name.lower()))
            name_scores.append(fuzz.ratio(event_loc.name.lower(), entity.name.lower()))

        if event.location_mentioned:
            name_scores.append(fuzz.partial_ratio(event.location_mentioned.lower(), entity.name.lower()))
            name_scores.append(fuzz.partial_ratio(event.location_mentioned.lower(), entity.location.lower()))

        for ext in event.extracted_entities:
            name_scores.append(fuzz.ratio(ext.lower(), entity.name.lower()))
            name_scores.append(fuzz.partial_ratio(ext.lower(), entity.name.lower()))

        lexical_similarity = (max(name_scores) / 100.0) if name_scores else 0.0
        if lexical_similarity >= 0.70:
            reasons.append(f"Strong name similarity: {int(lexical_similarity * 100)}%")

        # 5. Composite Geo-Confidence Score
        # Component weights:
        # Lexical place-name similarity: 30%
        # Administrative consistency: 35%
        # Geographic proximity: 25%
        # Entity context compatibility: 10%
        admin_score = 0.0
        if country_match:
            admin_score += 0.25
        if state_match:
            admin_score += 0.35
        if city_match:
            admin_score += 0.40

        # Entity type compatibility
        type_score = 0.5
        if event.event_type in ["flood", "weather"] and entity.type in ["factory", "warehouse", "route"]:
            type_score = 1.0
        elif event.event_type in ["strike", "closure"] and entity.type in ["supplier", "factory", "warehouse"]:
            type_score = 1.0

        geo_confidence = (
            (lexical_similarity * 0.30)
            + (admin_score * 0.35)
            + (distance_score * 0.25)
            + (type_score * 0.10)
        )
        geo_confidence = round(min(1.0, max(0.0, geo_confidence)), 4)

        status: str = "REJECTED"
        if geo_confidence >= 0.65:
            status = "MATCH"
        elif geo_confidence >= 0.45:
            status = "AMBIGUOUS"

        return GeoMatchCandidate(
            entity_id=entity.id,
            entity_name=entity.name,
            entity_type=entity.type,
            entity_location=entity.location,
            entity_latitude=ent_lat,
            entity_longitude=ent_lon,
            distance_km=distance_km,
            city_match=city_match,
            state_match=state_match,
            country_match=country_match,
            name_similarity=round(lexical_similarity, 3),
            geo_confidence=geo_confidence,
            status=status,
            match_reasons=reasons,
        )

    def verify_and_match(
        self, event: DisruptionEvent, entities: Optional[List[BusinessEntity]] = None
    ) -> GeoVerificationResult:
        """Executes full geographic verification, place resolution, distance calculation,

        and candidate disambiguation.
        """
        if entities is None:
            entities = self.network_service.list_entities()

        # Step 1: Resolve event location
        raw_loc_str = event.location_mentioned or ""
        event_loc = self.geocoding_service.resolve_place(raw_loc_str)

        # Update event model fields for transparency
        event.event_latitude = event_loc.latitude
        event.event_longitude = event_loc.longitude
        event.event_city = event_loc.city
        event.event_state = event_loc.state
        event.event_country = event_loc.country
        event.location_confidence = event_loc.confidence

        if not entities:
            return GeoVerificationResult(
                event_id=event.id,
                event_location=event_loc,
                status="LOCATION_UNRESOLVED" if not event_loc.is_resolved else "LOCATION_VERIFIED",
                location_confidence=round(event_loc.confidence * 100.0, 1),
                entity_match_confidence=0.0,
                ambiguity_reason="No business entities configured in network.",
            )

        # Step 2: Evaluate all candidate entities
        candidates: List[GeoMatchCandidate] = []
        for entity in entities:
            candidate = self.evaluate_candidate(event_loc, event, entity)
            candidates.append(candidate)

        # Sort candidates by geo_confidence descending
        candidates.sort(key=lambda c: c.geo_confidence, reverse=True)

        if not candidates or candidates[0].geo_confidence < 0.40:
            # No viable candidate
            status = "LOCATION_UNRESOLVED" if not event_loc.is_resolved else "LOCATION_PARTIALLY_VERIFIED"
            return GeoVerificationResult(
                event_id=event.id,
                event_location=event_loc,
                status=status,
                location_confidence=round(event_loc.confidence * 100.0, 1),
                entity_match_confidence=round((candidates[0].geo_confidence if candidates else 0.0) * 100.0, 1),
                primary_matched_entity_id=None,
                candidates=candidates,
                ambiguity_reason="No business entities met minimum geographic confidence threshold.",
            )

        top_candidate = candidates[0]
        second_candidate = candidates[1] if len(candidates) > 1 else None

        # Step 3: Ambiguity Detection & Disambiguation
        is_ambiguous = False
        ambiguity_reason = None

        if second_candidate is not None:
            score_diff = top_candidate.geo_confidence - second_candidate.geo_confidence
            # If two candidates have close scores
            if score_diff < self.config.ambiguity_threshold:
                # If candidates have similar names or viable match scores without geographic distinction
                if top_candidate.geo_confidence >= 0.35 or top_candidate.name_similarity >= 0.60:
                    is_ambiguous = True
                    ambiguity_reason = (
                        f"Ambiguous entity candidates with close confidence delta ({score_diff:.2f}): "
                        f"'{top_candidate.entity_name}' ({top_candidate.entity_location}, score {top_candidate.geo_confidence:.2f}) "
                        f"vs '{second_candidate.entity_name}' ({second_candidate.entity_location}, score {second_candidate.geo_confidence:.2f}). "
                        f"Manual analyst review required."
                    )
            # Check for multiple entities in same city or within very close distance (e.g. 5 km) with similar names
            elif (
                top_candidate.distance_km is not None
                and second_candidate.distance_km is not None
                and abs(top_candidate.distance_km - second_candidate.distance_km) < 10.0
                and second_candidate.name_similarity > 0.70
            ):
                is_ambiguous = True
                ambiguity_reason = (
                    f"Multiple proximate facilities detected in close range: "
                    f"'{top_candidate.entity_name}' ({top_candidate.distance_km:.1f}km) and "
                    f"'{second_candidate.entity_name}' ({second_candidate.distance_km:.1f}km)."
                )

        if is_ambiguous:
            # Mark all top candidates as AMBIGUOUS
            top_candidate.status = "AMBIGUOUS"
            if second_candidate:
                second_candidate.status = "AMBIGUOUS"

            return GeoVerificationResult(
                event_id=event.id,
                event_location=event_loc,
                status="LOCATION_AMBIGUOUS",
                location_confidence=round(event_loc.confidence * 100.0, 1),
                entity_match_confidence=round(top_candidate.geo_confidence * 100.0, 1),
                primary_matched_entity_id=None,  # Do not choose one! Failure-safe
                primary_matched_entity_name=None,
                distance_km=top_candidate.distance_km,
                candidates=candidates,
                ambiguity_reason=ambiguity_reason,
            )

        # Step 4: High-confidence Unambiguous Match
        if event_loc.is_resolved and top_candidate.geo_confidence >= self.config.min_geo_confidence:
            status = "LOCATION_VERIFIED"
        else:
            status = "LOCATION_PARTIALLY_VERIFIED"

        top_candidate.status = "MATCH"
        return GeoVerificationResult(
            event_id=event.id,
            event_location=event_loc,
            status=status,
            location_confidence=round(event_loc.confidence * 100.0, 1),
            entity_match_confidence=round(top_candidate.geo_confidence * 100.0, 1),
            primary_matched_entity_id=top_candidate.entity_id,
            primary_matched_entity_name=top_candidate.entity_name,
            distance_km=top_candidate.distance_km,
            candidates=candidates,
            ambiguity_reason=None,
        )


# Singleton
_geo_matching_service_instance: Optional[GeoMatchingService] = None


def get_geo_matching_service() -> GeoMatchingService:
    global _geo_matching_service_instance
    if _geo_matching_service_instance is None:
        _geo_matching_service_instance = GeoMatchingService()
    return _geo_matching_service_instance
