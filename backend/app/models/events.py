from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RawSearchResult(BaseModel):
    """Internal model capturing Tavily research agent search output.

    Preserves full URL attribution and query string for complete lineage and traceability.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    url: str = Field(..., description="Source web URL for attribution")
    title: str = Field(..., description="Title of retrieved web article/snippet")
    snippet: str = Field(..., description="Raw text snippet retrieved")
    queried_entity_id: str = Field(..., description="ID of entity for which search was generated")
    query_used: str = Field(..., description="Literal query string dispatched to Tavily")
    published_at: Optional[datetime] = Field(
        default=None,
        description="Article publication date from Tavily `published_date` (None if unavailable)",
    )
    retrieved_at: datetime = Field(default_factory=utcnow)


class DisruptionEvent(BaseModel):
    """Structured disruption event extracted by the Analysis Agent (LLM + Pydantic).

    Contains structured event details and explicit false-positive relevance verdict.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_url: str = Field(..., description="Source web article URL")
    source_result_id: str = Field(..., description="ID of parent RawSearchResult")
    headline: str = Field(..., description="Extracted event headline")
    summary: str = Field(..., max_length=500, description="Structured 1-2 sentence summary")
    event_type: Literal[
        "flood", "strike", "closure", "supplier_failure", "political", "weather", "other"
    ] = Field(..., description="Categorized disruption type")
    location_mentioned: str = Field(..., description="Location explicitly mentioned in text")
    severity_raw: Literal["low", "medium", "high", "unclear"] = Field(
        ..., description="Extracted disruption severity"
    )
    extracted_entities: list[str] = Field(
        default_factory=list, description="List of entity names mentioned in article text"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="LLM extraction confidence score (0.0 to 1.0)"
    )
    is_relevant: bool = Field(
        ..., description="False-positive filter: True if active disruption, False if averted/irrelevant"
    )
    published_at: Optional[datetime] = Field(
        default=None,
        description="Publication date propagated from source RawSearchResult (None if unavailable)",
    )
    retrieved_at: datetime = Field(default_factory=utcnow)
    analyzed_at: datetime = Field(default_factory=utcnow)
    # Phase G — credibility link (optional; populated after VerificationService runs)
    credibility_assessment_id: Optional[str] = Field(
        default=None,
        description="ID of associated CredibilityAssessment (populated after verification stage)",
    )
    # Geospatial verification link & structured location
    geo_verification_id: Optional[str] = Field(
        default=None,
        description="ID of associated GeoVerificationResult (populated after geo verification stage)",
    )
    event_latitude: Optional[float] = Field(
        default=None, ge=-90.0, le=90.0, description="Resolved event latitude"
    )
    event_longitude: Optional[float] = Field(
        default=None, ge=-180.0, le=180.0, description="Resolved event longitude"
    )
    event_city: Optional[str] = Field(default=None, description="Extracted / normalized event city")
    event_state: Optional[str] = Field(default=None, description="Extracted / normalized event state")
    event_country: Optional[str] = Field(default=None, description="Extracted / normalized event country")
    location_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Location resolution confidence score (0.0 to 1.0)"
    )


class MatchedImpact(BaseModel):
    """Output of Entity Matcher mapping a DisruptionEvent to Network Graph nodes."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str = Field(..., description="ID of matching DisruptionEvent")
    matched_entity_ids: list[str] = Field(
        default_factory=list, description="Entity IDs directly matching event"
    )
    match_confidence: float = Field(..., ge=0.0, le=1.0, description="Combined geo/fuzzy match confidence score")
    downstream_entity_ids: list[str] = Field(
        default_factory=list, description="Downstream entity IDs retrieved via graph traversal"
    )
    geo_status: Optional[str] = Field(
        default=None, description="Geographic verification status (LOCATION_VERIFIED, LOCATION_AMBIGUOUS, etc.)"
    )
    ambiguity_reason: Optional[str] = Field(
        default=None, description="Reason if location or entity matching was ambiguous"
    )
    matched_at: datetime = Field(default_factory=utcnow)
