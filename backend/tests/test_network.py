import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.entity import BusinessEntity, BusinessRelationship, EntityMetadata
from app.services.network_service import NetworkService, get_network_service


@pytest.fixture
def clean_network_service():
    """Provides a fresh NetworkService instance for isolated unit testing."""
    service = NetworkService()
    return service


def test_network_service_graph_traversal(clean_network_service):
    service = clean_network_service

    # Create entities: Supplier -> Factory -> Warehouse -> Customer
    supplier = service.add_entity(
        BusinessEntity(
            id="supp-1",
            name="Lithium Supplier Corp",
            type="supplier",
            location="Santiago, Chile",
            criticality="high",
            metadata=EntityMetadata(lead_time_days=30, alternative_supplier_available=False),
        )
    )
    factory = service.add_entity(
        BusinessEntity(
            id="fact-1",
            name="Battery Gigafactory",
            type="factory",
            location="Berlin, Germany",
            criticality="high",
            metadata=EntityMetadata(lead_time_days=14, alternative_supplier_available=True),
        )
    )
    warehouse = service.add_entity(
        BusinessEntity(
            id="ware-1",
            name="EU Central Warehouse",
            type="warehouse",
            location="Rotterdam, Netherlands",
            criticality="medium",
        )
    )
    customer = service.add_entity(
        BusinessEntity(
            id="cust-1",
            name="Auto Manufacturer EV",
            type="customer",
            location="Munich, Germany",
            criticality="high",
        )
    )

    # Add dependencies:
    # Factory depends on Supplier
    service.add_relationship(
        BusinessRelationship(
            id="rel-1",
            source_id="fact-1",
            target_id="supp-1",
            relationship_type="supplies",
            dependency_weight=0.9,
        )
    )
    # Warehouse depends on Factory
    service.add_relationship(
        BusinessRelationship(
            id="rel-2",
            source_id="ware-1",
            target_id="fact-1",
            relationship_type="ships_to",
            dependency_weight=0.8,
        )
    )
    # Customer depends on Warehouse
    service.add_relationship(
        BusinessRelationship(
            id="rel-3",
            source_id="cust-1",
            target_id="ware-1",
            relationship_type="ships_to",
            dependency_weight=1.0,
        )
    )

    # Test downstream traversal from supplier (depth=3)
    downstream_depth3 = service.get_downstream("supp-1", max_depth=3)
    downstream_ids3 = {e.id for e in downstream_depth3}
    assert downstream_ids3 == {"fact-1", "ware-1", "cust-1"}

    # Test downstream traversal from supplier (depth=1)
    downstream_depth1 = service.get_downstream("supp-1", max_depth=1)
    downstream_ids1 = {e.id for e in downstream_depth1}
    assert downstream_ids1 == {"fact-1"}


def test_network_graph_api_format():
    client = TestClient(app)
    response = client.get("/api/network")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
