"""Section A — Business Network Service Edge-Case Tests.

Tests A1–A8 from the full-system test matrix.
"""

import time
import pytest
from pydantic import ValidationError

from app.models.entity import BusinessEntity, BusinessRelationship, EntityMetadata
from app.services.network_service import NetworkService


# Import shared helpers
from tests.conftest import make_entity, make_relationship


# ===========================================================================
# A1: Add relationship referencing a nonexistent entity
# Type: Integration
# ===========================================================================
class TestA1NonexistentEntityRelationship:
    def test_relationship_to_nonexistent_target_raises_valueerror(self, fresh_network):
        """A1: Adding a relationship with nonexistent entity returns clear ValueError, not raw NetworkX exception."""
        svc = fresh_network
        svc.add_entity(make_entity(id="ent-exists", name="Existing Entity"))
        with pytest.raises(ValueError, match="does not exist"):
            svc.add_relationship(make_relationship(
                id="rel-bad", source_id="ent-exists", target_id="ent-MISSING",
            ))

    def test_relationship_from_nonexistent_source_raises_valueerror(self, fresh_network):
        """A1b: Source entity also validated."""
        svc = fresh_network
        svc.add_entity(make_entity(id="ent-exists", name="Existing"))
        with pytest.raises(ValueError, match="does not exist"):
            svc.add_relationship(make_relationship(
                id="rel-bad", source_id="ent-MISSING", target_id="ent-exists",
            ))


# ===========================================================================
# A2: Relationship with source_id == target_id
# Type: Unit
# ===========================================================================
class TestA2SelfLoop:
    def test_self_loop_rejected_by_pydantic_validator(self):
        """A2: model_validator on BusinessRelationship rejects self-loop before reaching the service."""
        with pytest.raises(ValidationError, match="cannot depend on itself"):
            BusinessRelationship(
                source_id="ent-same",
                target_id="ent-same",
                relationship_type="supplies",
                dependency_weight=0.5,
            )


# ===========================================================================
# A3: Remove entity that has existing relationships
# Type: Integration
# ===========================================================================
class TestA3RemoveEntityCascade:
    def test_removing_entity_cascades_relationships(self, fresh_network):
        """A3: Removing an entity also removes its associated relationship edges.
        
        Documented behavior: cascade-delete relationships (confirmed from network_service.remove_entity).
        """
        svc = fresh_network
        svc.add_entity(make_entity(id="ent-a", name="Entity A"))
        svc.add_entity(make_entity(id="ent-b", name="Entity B"))
        svc.add_entity(make_entity(id="ent-c", name="Entity C"))
        svc.add_relationship(make_relationship(id="rel-ab", source_id="ent-a", target_id="ent-b"))
        svc.add_relationship(make_relationship(id="rel-bc", source_id="ent-b", target_id="ent-c"))

        assert len(svc.list_relationships()) == 2
        # Remove entity B — should cascade-remove rel-ab and rel-bc
        svc.remove_entity("ent-b")
        remaining_rels = svc.list_relationships()
        assert len(remaining_rels) == 0, (
            f"Expected 0 remaining relationships after cascade, got {len(remaining_rels)}"
        )
        assert svc.get_entity("ent-b") is None
        # Other entities survive
        assert svc.get_entity("ent-a") is not None
        assert svc.get_entity("ent-c") is not None

    def test_removing_nonexistent_entity_raises_keyerror(self, fresh_network):
        """A3b: Removing a non-existent entity is a clear error."""
        with pytest.raises(KeyError):
            fresh_network.remove_entity("ent-nonexistent")


# ===========================================================================
# A4: get_downstream on isolated node
# Type: Unit
# ===========================================================================
class TestA4IsolatedNodeDownstream:
    def test_isolated_node_returns_empty_list(self, fresh_network):
        """A4: Node with no outgoing edges returns [], not an error."""
        svc = fresh_network
        svc.add_entity(make_entity(id="ent-isolated", name="Isolated"))
        result = svc.get_downstream("ent-isolated")
        assert result == []

    def test_nonexistent_node_returns_empty_list(self, fresh_network):
        """A4b: Node not in graph returns []."""
        assert fresh_network.get_downstream("ent-does-not-exist") == []


# ===========================================================================
# A5: get_downstream with a cycle
# Type: Unit
# ===========================================================================
class TestA5CyclicGraph:
    def test_cycle_terminates_without_infinite_loop(self, fresh_network):
        """A5: Cycle A→B→C→A terminates correctly, no duplicates."""
        svc = fresh_network
        svc.add_entity(make_entity(id="cycle-a", name="A"))
        svc.add_entity(make_entity(id="cycle-b", name="B"))
        svc.add_entity(make_entity(id="cycle-c", name="C"))
        svc.add_relationship(make_relationship(id="r1", source_id="cycle-a", target_id="cycle-b"))
        svc.add_relationship(make_relationship(id="r2", source_id="cycle-b", target_id="cycle-c"))
        svc.add_relationship(make_relationship(id="r3", source_id="cycle-c", target_id="cycle-a"))

        downstream = svc.get_downstream("cycle-a", max_depth=10)
        downstream_ids = [e.id for e in downstream]
        # Should terminate and not duplicate
        assert len(downstream_ids) == len(set(downstream_ids)), "Duplicates found in cycle traversal"
        # Should find B and C as downstream
        assert set(downstream_ids) == {"cycle-b", "cycle-c"}


# ===========================================================================
# A6: get_downstream(max_depth=0)
# Type: Unit
# ===========================================================================
class TestA6DepthZero:
    def test_depth_zero_returns_empty(self, populated_network):
        """A6: max_depth=0 returns []."""
        result = populated_network.get_downstream("supp-1", max_depth=0)
        assert result == []


# ===========================================================================
# A7: Large network performance
# Type: Integration
# ===========================================================================
class TestA7LargeNetwork:
    def test_large_network_responds_in_reasonable_time(self, fresh_network):
        """A7: Network with 100+ entities and relationships responds within 1 second."""
        svc = fresh_network
        # Create 100 entities
        for i in range(100):
            svc.add_entity(make_entity(
                id=f"ent-{i}", name=f"Entity {i}",
                location=f"City {i}, Country",
            ))
        # Create chain relationships
        for i in range(99):
            svc.add_relationship(make_relationship(
                id=f"rel-{i}", source_id=f"ent-{i}", target_id=f"ent-{i+1}",
            ))

        # Time get_downstream
        start = time.perf_counter()
        downstream = svc.get_downstream("ent-50", max_depth=5)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Time to_graph_json
        start2 = time.perf_counter()
        graph_json = svc.to_graph_json()
        elapsed_json_ms = (time.perf_counter() - start2) * 1000

        assert elapsed_ms < 1000, f"get_downstream took {elapsed_ms:.1f}ms (limit: 1000ms)"
        assert elapsed_json_ms < 1000, f"to_graph_json took {elapsed_json_ms:.1f}ms (limit: 1000ms)"
        assert len(graph_json["nodes"]) == 100
        assert len(graph_json["edges"]) == 99
        # Record actual timing for the report
        print(f"\n[A7 PERF] get_downstream: {elapsed_ms:.1f}ms, to_graph_json: {elapsed_json_ms:.1f}ms")


# ===========================================================================
# A8: Duplicate entity names
# Type: Unit
# ===========================================================================
class TestA8DuplicateNames:
    def test_two_entities_same_name_different_ids_allowed(self, fresh_network):
        """A8: Duplicate names are allowed — IDs are the real identity."""
        svc = fresh_network
        svc.add_entity(make_entity(id="ent-1a", name="Duplicate Name", location="Location A"))
        svc.add_entity(make_entity(id="ent-1b", name="Duplicate Name", location="Location B"))
        entities = svc.list_entities()
        assert len(entities) == 2
        names = [e.name for e in entities]
        assert names.count("Duplicate Name") == 2
        # IDs must be distinct
        ids = [e.id for e in entities]
        assert len(set(ids)) == 2

    def test_downstream_works_with_duplicate_names(self, fresh_network):
        """A8b: Downstream traversal works correctly when names are duplicated."""
        svc = fresh_network
        svc.add_entity(make_entity(id="dup-1", name="Same Name", location="Loc A"))
        svc.add_entity(make_entity(id="dup-2", name="Same Name", location="Loc B"))
        svc.add_entity(make_entity(id="dup-3", name="Different Name", location="Loc C"))
        svc.add_relationship(make_relationship(id="r1", source_id="dup-2", target_id="dup-1"))
        svc.add_relationship(make_relationship(id="r2", source_id="dup-3", target_id="dup-2"))

        downstream = svc.get_downstream("dup-1", max_depth=3)
        downstream_ids = {e.id for e in downstream}
        assert "dup-2" in downstream_ids
        assert "dup-3" in downstream_ids
