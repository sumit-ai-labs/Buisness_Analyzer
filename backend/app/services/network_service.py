from typing import Dict, List, Optional
import networkx as nx

from app.core.logging import logger
from app.models.entity import BusinessEntity, BusinessRelationship


class NetworkService:
    """In-memory Business Network Graph Service powered by NetworkX DiGraph.

    Nodes represent BusinessEntities (suppliers, factories, warehouses, routes, customers).
    Directed edges represent BusinessRelationships (source -> target dependency).
    Downstream graph traversal finds entities that depend directly or indirectly on a node.
    """

    def __init__(self):
        self.graph: nx.DiGraph = nx.DiGraph()
        self._entities: Dict[str, BusinessEntity] = {}
        self._relationships: Dict[str, BusinessRelationship] = {}

    def add_entity(self, entity: BusinessEntity) -> BusinessEntity:
        """Adds or updates a BusinessEntity node in the graph."""
        self._entities[entity.id] = entity
        self.graph.add_node(
            entity.id,
            name=entity.name,
            type=entity.type,
            location=entity.location,
            criticality=entity.criticality,
            status=entity.status,
        )
        logger.info(f"Added entity to network graph: {entity.name} (id={entity.id}, type={entity.type})")
        return entity

    def get_entity(self, entity_id: str) -> Optional[BusinessEntity]:
        """Retrieves an entity by ID."""
        return self._entities.get(entity_id)

    def list_entities(self) -> List[BusinessEntity]:
        """Lists all registered business entities."""
        return list(self._entities.values())

    def update_entity(self, entity_id: str, patch: dict) -> BusinessEntity:
        """Updates entity fields dynamically and updates graph node metadata."""
        entity = self.get_entity(entity_id)
        if not entity:
            raise KeyError(f"Entity with ID {entity_id} not found")

        updated_data = entity.model_dump()
        for key, value in patch.items():
            if value is not None and key in updated_data:
                updated_data[key] = value

        updated_entity = BusinessEntity(**updated_data)
        self.add_entity(updated_entity)
        return updated_entity

    def remove_entity(self, entity_id: str) -> None:
        """Removes an entity node and all associated relationship edges from graph."""
        if entity_id not in self._entities:
            raise KeyError(f"Entity with ID {entity_id} not found")

        del self._entities[entity_id]
        if self.graph.has_node(entity_id):
            self.graph.remove_node(entity_id)

        # Remove relationships associated with this entity
        rel_ids_to_remove = [
            rel_id
            for rel_id, rel in self._relationships.items()
            if rel.source_id == entity_id or rel.target_id == entity_id
        ]
        for rel_id in rel_ids_to_remove:
            del self._relationships[rel_id]

        logger.info(f"Removed entity {entity_id} and {len(rel_ids_to_remove)} associated relationships")

    def add_relationship(self, rel: BusinessRelationship) -> BusinessRelationship:
        """Adds a directed dependency relationship between two entities.

        Validates that both source and target entities exist in the graph.
        """
        if rel.source_id not in self._entities:
            raise ValueError(f"Source entity ID '{rel.source_id}' does not exist.")
        if rel.target_id not in self._entities:
            raise ValueError(f"Target entity ID '{rel.target_id}' does not exist.")

        self._relationships[rel.id] = rel
        # Directed edge: target_id -> source_id (supplier points to dependent entity)
        # or source_id -> target_id according to dependency orientation
        self.graph.add_edge(
            rel.source_id,
            rel.target_id,
            id=rel.id,
            relationship_type=rel.relationship_type,
            dependency_weight=rel.dependency_weight,
        )
        logger.info(
            f"Added relationship: {rel.source_id} --[{rel.relationship_type}, weight={rel.dependency_weight}]--> {rel.target_id}"
        )
        return rel

    def list_relationships(self) -> List[BusinessRelationship]:
        """Lists all active relationships."""
        return list(self._relationships.values())

    def remove_relationship(self, rel_id: str) -> None:
        """Removes a relationship edge by ID."""
        if rel_id not in self._relationships:
            raise KeyError(f"Relationship with ID {rel_id} not found")

        rel = self._relationships[rel_id]
        del self._relationships[rel_id]
        if self.graph.has_edge(rel.source_id, rel.target_id):
            self.graph.remove_edge(rel.source_id, rel.target_id)
        logger.info(f"Removed relationship {rel_id}")

    def get_downstream(self, entity_id: str, max_depth: int = 3) -> List[BusinessEntity]:
        """Performs BFS graph traversal to find downstream entities affected if entity_id is disrupted.

        Traverses edges where source_id depends on target_id (or reverse path depending on edge orientation).
        In our DiGraph, if entity B depends on entity A (A supplies B), an issue at A impacts B.
        So we find all node 'v' where source_id == v and target_id == entity_id (predecessors/successors).
        """
        if entity_id not in self._entities:
            return []

        downstream_ids = set()
        visited = {entity_id: 0}
        queue = [(entity_id, 0)]

        while queue:
            current_node, depth = queue.pop(0)
            if depth >= max_depth:
                continue

            # Hierarchy order to prevent upstream leakage:
            # Disruptions only propagate downstream in the supply chain.
            # Higher-tier nodes (e.g. factory, warehouse, customer) never propagate backwards to lower-tier suppliers.
            tier_order = {
                "supplier": 0,
                "route": 1,
                "factory": 2,
                "warehouse": 3,
                "customer": 4,
            }

            current_ent = self._entities.get(current_node)
            curr_tier = tier_order.get(current_ent.type) if current_ent else None

            dependent_neighbors = set()
            for u, v, data in self.graph.edges(data=True):
                cand = None
                if v == current_node:
                    cand = u
                elif u == current_node:
                    cand = v

                if cand and cand not in visited and cand != entity_id:
                    cand_ent = self._entities.get(cand)
                    cand_tier = tier_order.get(cand_ent.type) if cand_ent else None
                    if curr_tier is not None and cand_tier is not None and curr_tier > cand_tier:
                        # Prevent backward upstream propagation (e.g. factory disruption cannot affect supplier)
                        continue
                    dependent_neighbors.add(cand)

            for neighbor in dependent_neighbors:
                if neighbor not in visited and neighbor != entity_id:
                    visited[neighbor] = depth + 1
                    downstream_ids.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return [self._entities[nid] for nid in downstream_ids if nid in self._entities]

    def to_graph_json(self) -> dict:
        """Serializes network topology to React Flow compatible JSON format ({ nodes: [...], edges: [...] })."""
        nodes = []
        for entity_id, entity in self._entities.items():
            nodes.append(
                {
                    "id": entity.id,
                    "type": "customEntityNode",
                    "data": {
                        "label": entity.name,
                        "entityType": entity.type,
                        "location": entity.location,
                        "criticality": entity.criticality,
                        "status": entity.status,
                        "leadTimeDays": entity.metadata.lead_time_days,
                        "altSupplierAvailable": entity.metadata.alternative_supplier_available,
                    },
                }
            )

        edges = []
        for rel_id, rel in self._relationships.items():
            edges.append(
                {
                    "id": rel.id,
                    "source": rel.source_id,
                    "target": rel.target_id,
                    "label": f"{rel.relationship_type} ({rel.dependency_weight * 100:.0f}%)",
                    "data": {
                        "relationshipType": rel.relationship_type,
                        "dependencyWeight": rel.dependency_weight,
                    },
                }
            )

        return {"nodes": nodes, "edges": edges}


# Singleton service instance dependency
network_service_instance = NetworkService()


def get_network_service() -> NetworkService:
    """FastAPI Dependency injector for NetworkService singleton."""
    return network_service_instance
