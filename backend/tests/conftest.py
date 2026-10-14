"""Shared fixtures and helpers for the full-system test suite.

Provides reusable entity, event, and network builders used across
test_network.py, test_analysis.py, test_verification.py, test_geo.py,
test_risk_engine.py, test_alerts.py, test_e2e.py.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from app.models.entity import BusinessEntity, BusinessRelationship, EntityMetadata
from app.models.events import DisruptionEvent, RawSearchResult
from app.services.network_service import NetworkService


# ---------------------------------------------------------------------------
# Entity Factories
# ---------------------------------------------------------------------------

def make_entity(
    id: str = "ent-1",
    name: str = "Test Entity",
    type: str = "supplier",
    location: str = "Mumbai, India",
    criticality: str = "high",
    lat: float | None = None,
    lon: float | None = None,
    lead_time_days: int | None = None,
    alt_supplier: bool = False,
    city: str | None = None,
    state: str | None = None,
    country: str | None = None,
) -> BusinessEntity:
    return BusinessEntity(
        id=id,
        name=name,
        type=type,
        location=location,
        criticality=criticality,
        latitude=lat,
        longitude=lon,
        metadata=EntityMetadata(
            lead_time_days=lead_time_days,
            alternative_supplier_available=alt_supplier,
        ),
        city=city,
        state=state,
        country=country,
    )


def make_event(
    source_url: str = "https://reuters.com/article-1",
    event_type: str = "flood",
    location_mentioned: str = "Mumbai",
    confidence: float = 0.85,
    headline: str = "Flood disrupts supply routes",
    summary: str = "Flood event reported in Mumbai affecting logistics.",
    severity_raw: str = "medium",
    is_relevant: bool = True,
    source_result_id: str = "res-test",
    extracted_entities: list[str] | None = None,
) -> DisruptionEvent:
    return DisruptionEvent(
        source_url=source_url,
        source_result_id=source_result_id,
        headline=headline,
        summary=summary,
        event_type=event_type,
        location_mentioned=location_mentioned,
        severity_raw=severity_raw,
        confidence=confidence,
        is_relevant=is_relevant,
        extracted_entities=extracted_entities or [],
    )


def make_raw_result(
    url: str = "https://example.com/article",
    entity_id: str = "ent-1",
    published_at: datetime | None = None,
) -> RawSearchResult:
    return RawSearchResult(
        url=url,
        title="Test Article",
        snippet="Something happened.",
        queried_entity_id=entity_id,
        query_used="test query",
        published_at=published_at,
    )


def make_relationship(
    id: str = "rel-1",
    source_id: str = "ent-a",
    target_id: str = "ent-b",
    rel_type: str = "supplies",
    weight: float = 0.9,
) -> BusinessRelationship:
    return BusinessRelationship(
        id=id,
        source_id=source_id,
        target_id=target_id,
        relationship_type=rel_type,
        dependency_weight=weight,
    )


# ---------------------------------------------------------------------------
# Network Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_network():
    """Provides a clean NetworkService instance for isolated testing."""
    return NetworkService()


@pytest.fixture
def populated_network():
    """Provides a NetworkService with a standard 4-entity linear chain:
    Supplier -> Factory -> Warehouse -> Customer
    """
    svc = NetworkService()
    svc.add_entity(make_entity(
        id="supp-1", name="Raw Material Supplier", type="supplier",
        location="Santiago, Chile", criticality="high",
    ))
    svc.add_entity(make_entity(
        id="fact-1", name="Assembly Factory", type="factory",
        location="Berlin, Germany", criticality="high",
        lead_time_days=14, alt_supplier=True,
    ))
    svc.add_entity(make_entity(
        id="ware-1", name="Central Warehouse", type="warehouse",
        location="Rotterdam, Netherlands", criticality="medium",
    ))
    svc.add_entity(make_entity(
        id="cust-1", name="End Customer", type="customer",
        location="Munich, Germany", criticality="high",
    ))
    svc.add_relationship(make_relationship(
        id="rel-1", source_id="fact-1", target_id="supp-1",
        rel_type="supplies", weight=0.9,
    ))
    svc.add_relationship(make_relationship(
        id="rel-2", source_id="ware-1", target_id="fact-1",
        rel_type="ships_to", weight=0.8,
    ))
    svc.add_relationship(make_relationship(
        id="rel-3", source_id="cust-1", target_id="ware-1",
        rel_type="ships_to", weight=1.0,
    ))
    return svc
