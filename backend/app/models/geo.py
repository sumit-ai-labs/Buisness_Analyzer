"""Geospatial and Location Data Models.

Defines schemas for:
- Canonical geographic coordinates with bounds validation and accuracy.
- Structured event location extraction.
- Entity geo-matching candidate evidence and disambiguation results.
- User/device location signal (strictly decoupled from event location).
- System-wide geographic intelligence configuration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


GeoStatus = Literal[
    "LOCATION_VERIFIED",
    "LOCATION_PARTIALLY_VERIFIED",
    "LOCATION_AMBIGUOUS",
    "LOCATION_UNRESOLVED",
]

CandidateMatchStatus = Literal[
    "MATCH",
    "AMBIGUOUS",
    "REJECTED",
    "UNRESOLVED",
]


class GeoCoordinate(BaseModel):
    """Canonical geographic coordinate with validation and accuracy."""

    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees (-90 to +90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees (-180 to +180)")
    accuracy_m: Optional[float] = Field(default=None, ge=0.0, description="Estimated accuracy radius in meters")
    source: str = Field(default="geocoded", description="Source of coordinate (e.g., 'nominatim', 'configured', 'gps')")
    timestamp: datetime = Field(default_factory=_utcnow)

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90; got {v}")
        return round(v, 6)

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180; got {v}")
        return round(v, 6)


class EventLocation(BaseModel):
    """Structured location extracted and resolved for a disruption event."""

    raw_text: str = Field(..., description="Raw text snippet or place string extracted from event")
    name: Optional[str] = Field(default=None, description="Resolved specific landmark or industrial area name")
    city: Optional[str] = Field(default=None, description="Resolved city name")
    district: Optional[str] = Field(default=None, description="Resolved district/county")
    state: Optional[str] = Field(default=None, description="Resolved state/province")
    country: Optional[str] = Field(default=None, description="Resolved country")
    postal_code: Optional[str] = Field(default=None, description="Resolved postal code")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Location resolution confidence (0.0 to 1.0)",
    )
    source: str = Field(default="unresolved", description="Resolution source provider or fallback")
    is_resolved: bool = Field(default=False, description="True if coordinates were reliably resolved")

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 4)


class GeoMatchCandidate(BaseModel):
    """Detailed geographic comparison between an event location and candidate business entity."""

    entity_id: str = Field(..., description="ID of evaluated business entity")
    entity_name: str = Field(..., description="Name of evaluated business entity")
    entity_type: str = Field(..., description="Type of entity (supplier, factory, warehouse, etc.)")
    entity_location: str = Field(..., description="Entity configured location string")
    entity_latitude: Optional[float] = Field(default=None)
    entity_longitude: Optional[float] = Field(default=None)
    distance_km: Optional[float] = Field(default=None, description="Haversine distance in km")
    city_match: bool = Field(default=False, description="Whether event city matches entity city")
    state_match: bool = Field(default=False, description="Whether event state matches entity state")
    country_match: bool = Field(default=False, description="Whether event country matches entity country")
    name_similarity: float = Field(default=0.0, ge=0.0, le=1.0, description="Name/place string similarity (0.0 - 1.0)")
    geo_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Combined geo-match confidence (0.0 - 1.0)")
    status: CandidateMatchStatus = Field(default="REJECTED")
    match_reasons: List[str] = Field(default_factory=list, description="Explainable evidence factors")


class GeoVerificationResult(BaseModel):
    """Full geographic verification and disambiguation result for a DisruptionEvent.
    
    Decoupled from Credibility Assessment.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str = Field(..., description="ID of assessed DisruptionEvent")
    event_location: EventLocation
    status: GeoStatus = Field(default="LOCATION_UNRESOLVED")
    location_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Confidence that the event occurred at this location (0 - 100)",
    )
    entity_match_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Confidence that this event impacts the selected business entity (0 - 100)",
    )
    primary_matched_entity_id: Optional[str] = Field(
        default=None,
        description="ID of unambiguously matched business entity (null if ambiguous or unresolved)",
    )
    primary_matched_entity_name: Optional[str] = Field(default=None)
    distance_km: Optional[float] = Field(default=None)
    candidates: List[GeoMatchCandidate] = Field(default_factory=list)
    ambiguity_reason: Optional[str] = Field(default=None)
    verified_at: datetime = Field(default_factory=_utcnow)

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})


class UserDeviceLocation(BaseModel):
    """Client device location provided with explicit browser permission.
    
    STRICT PRIVACY: NEVER confused with event location; optional contextual signal only.
    """

    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    accuracy_m: float = Field(..., ge=0.0)
    timestamp: datetime = Field(default_factory=_utcnow)
    status: Literal["AVAILABLE", "DENIED", "UNAVAILABLE", "ACQUIRING"] = "AVAILABLE"


class GeoConfig(BaseModel):
    """System configuration for geographic intelligence and disambiguation."""

    geolocation_enabled: bool = True
    require_location_verification: bool = True
    max_acceptable_distance_km: float = 100.0
    ambiguity_threshold: float = 0.15  # Score delta below which 2 candidates are deemed ambiguous
    min_geo_confidence: float = 0.50
    geocoder_provider: str = "nominatim"
    cache_duration_seconds: int = 86400
