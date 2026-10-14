from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator


def utcnow() -> datetime:
    """Utility function to get timezone-aware UTC current datetime."""
    return datetime.now(timezone.utc)


class EntityMetadata(BaseModel):
    """Metadata attached to a business entity providing operational context.

    Fields feed directly into downstream risk calculation formulas (lead_time_days,
    alternative_supplier_available).
    """

    lead_time_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Lead time required in days to replace or adjust supply from this entity",
    )
    alternative_supplier_available: bool = Field(
        default=False,
        description="Whether a pre-qualified alternative supplier/facility is available",
    )
    monthly_volume_units: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated monthly unit throughput volume",
    )
    notes: str = Field(default="", description="Free-text operational notes")


class BusinessEntity(BaseModel):
    """Represents a node in the business network graph (supplier, factory, warehouse, route, customer)."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=200, description="Name of entity/facility/supplier")
    type: Literal["supplier", "factory", "warehouse", "route", "customer"] = Field(
        ..., description="Entity category type"
    )
    location: str = Field(..., min_length=1, description="Geographic location (city/region/country)")
    criticality: Literal["low", "medium", "high"] = Field(
        ..., description="Business operational criticality level"
    )
    status: Literal["active", "inactive"] = Field(default="active", description="Active lifecycle status")
    metadata: EntityMetadata = Field(default_factory=EntityMetadata, description="Operational metadata")
    # Structured location & canonical GPS coordinates
    address: Optional[str] = Field(default=None, description="Detailed street address or industrial sector")
    city: Optional[str] = Field(default=None, description="Normalized city name")
    district: Optional[str] = Field(default=None, description="District or sub-region")
    state: Optional[str] = Field(default=None, description="State or province")
    country: Optional[str] = Field(default=None, description="Country name")
    postal_code: Optional[str] = Field(default=None, description="Postal / ZIP code")
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Canonical latitude (-90 to +90)")
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Canonical longitude (-180 to +180)")
    location_source: str = Field(default="configured", description="Origin of coordinates ('configured', 'geocoded', 'verified')")
    location_confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Reliability of entity coordinates (0.0 to 1.0)")

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class BusinessRelationship(BaseModel):
    """Represents a directed dependency edge in the business network graph.

    source_id depends on / receives supply from target_id according to relationship_type.
    dependency_weight: 0.0 (negligible) to 1.0 (total/sole dependency).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    source_id: str = Field(..., description="ID of dependent downstream entity")
    target_id: str = Field(..., description="ID of upstream supplier/facility entity")
    relationship_type: Literal["supplies", "ships_to", "stores_at", "depends_on"] = Field(
        ..., description="Dependency relationship type"
    )
    dependency_weight: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Weight of dependency (0.0 = negligible, 1.0 = sole supplier)",
    )
    created_at: datetime = Field(default_factory=utcnow)

    @model_validator(mode="after")
    def no_self_loop(self):
        """Enforces that an entity cannot have a dependency relationship pointing to itself."""
        if self.source_id == self.target_id:
            raise ValueError("An entity cannot depend on itself in a relationship.")
        return self
