"""Credibility Assessment Pydantic model — Phase D of Credibility Verification Engine.

CredibilityAssessment captures the full output of the Verification Service for a
single DisruptionEvent. It is immutable once created and provides an auditable,
factor-level breakdown of the credibility calculation.

Terminology:
    credibility / confidence / verification_status / unconfirmed
    — NOT "true", "false", "truth detector", "100% fake"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Credibility confidence labels
ConfidenceLabel = Literal["unconfirmed", "low", "moderate", "high"]

# Verification gate status
GateStatus = Literal["gated", "not_gated"]


class CredibilityAssessment(BaseModel):
    """Full credibility assessment for one DisruptionEvent.

    Fields
    ------
    id:
        Unique assessment identifier (UUID).
    event_id:
        ID of the assessed DisruptionEvent.
    source_domain:
        Normalised domain extracted from event.source_url.

    source_reputation_score:
        Raw lookup score from domain reputation table [0.0 – 1.0].
        Unknown domains receive 0.5 (neutral), never 0.
    source_tier:
        Human-readable tier label (e.g. "wire_service", "unverified").

    corroborating_source_count:
        Number of independent source domains that reported the same event.
    corroboration_score:
        Normalised corroboration value used in the formula [0.0 – 1.0].
        = min(count, 3) / 3.

    content_style_score:
        ML classifier output [0.0 – 1.0].
        Estimates textual similarity to "real news" class in training data.
        NOT a ground-truth truth probability. 0.5 when model unavailable.
    model_version:
        Version string of the credibility ML model used.

    llm_extraction_confidence:
        DisruptionEvent.confidence — the original LLM extraction confidence.
        This value is NOT recomputed; it is passed through unchanged.

    authenticity_score:
        Final weighted credibility score [0.0 – 100.0].
        Higher is more credible based on all combined signals.
    confidence_label:
        Human-readable bucket label derived from authenticity_score.
    is_gated:
        True if authenticity_score < GATE_THRESHOLD (35).
        Gated events are flagged "unconfirmed" but are NOT deleted.

    factors:
        Weighted contribution of each signal to the final score.
        Keys: source_reputation, corroboration, content_style,
              llm_extraction_confidence.

    computed_at:
        UTC timestamp of assessment.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_id: str = Field(..., description="ID of the assessed DisruptionEvent")
    source_domain: str = Field(..., description="Normalised source domain")

    # Signal 1: Source reputation
    source_reputation_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Domain reputation score (0.0–1.0); unknown domain = 0.5"
    )
    source_tier: str = Field(..., description="Domain tier (wire_service, established_news, …)")

    # Signal 2: Corroboration
    corroborating_source_count: int = Field(
        ..., ge=0,
        description="Number of independent domains reporting the same event"
    )
    corroboration_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="Normalised corroboration: min(count,3)/3"
    )

    # Signal 3: ML content style
    content_style_score: float = Field(
        ..., ge=0.0, le=1.0,
        description="ML classifier: P(real-news style) — NOT truth probability"
    )
    model_version: str = Field(
        ..., description="Version of the ML model used (or 'credibility-clf-unavailable')"
    )

    # Signal 4: LLM extraction confidence (pass-through)
    llm_extraction_confidence: float = Field(
        ..., ge=0.0, le=1.0,
        description="Original DisruptionEvent.confidence — LLM extraction quality"
    )

    # Final credibility result
    authenticity_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="Final weighted credibility score (0–100)"
    )
    confidence_label: ConfidenceLabel = Field(
        ...,
        description="Bucket label: high/moderate/low/unconfirmed"
    )
    is_gated: bool = Field(
        ...,
        description="True if score < 35 — event flagged unconfirmed but NOT deleted"
    )

    # Transparent factor breakdown
    factors: dict[str, float] = Field(
        ...,
        description="Weighted contributions of each signal to authenticity_score"
    )

    computed_at: datetime = Field(default_factory=_utcnow)

    @field_validator("authenticity_score")
    @classmethod
    def round_score(cls, v: float) -> float:
        return round(v, 2)

    @field_validator("factors")
    @classmethod
    def validate_factors(cls, v: dict) -> dict:
        """Ensure all factor values are floats rounded to 2dp."""
        return {k: round(float(val), 2) for k, val in v.items()}

    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
