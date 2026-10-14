export type EntityType = "supplier" | "factory" | "warehouse" | "route" | "customer";
export type CriticalityLevel = "low" | "medium" | "high";
export type EntityStatus = "active" | "inactive";

export interface EntityMetadata {
  lead_time_days?: number;
  alternative_supplier_available: boolean;
  monthly_volume_units?: number;
  notes?: string;
}

export interface BusinessEntity {
  id: string;
  name: string;
  type: EntityType;
  location: string;
  criticality: CriticalityLevel;
  status: EntityStatus;
  metadata: EntityMetadata;
  created_at?: string;
  updated_at?: string;
}

export type RelationshipType = "supplies" | "ships_to" | "stores_at" | "depends_on";

export interface BusinessRelationship {
  id: string;
  source_id: string;
  target_id: string;
  relationship_type: RelationshipType;
  dependency_weight: number;
  created_at?: string;
}

export interface GraphNodeData extends Record<string, unknown> {
  label: string;
  entityType: EntityType;
  location: string;
  criticality: CriticalityLevel;
  status: EntityStatus;
  leadTimeDays?: number;
  altSupplierAvailable: boolean;
  isAffected?: boolean;
}

export interface GraphNode {
  id: string;
  type: string;
  data: GraphNodeData;
  position?: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  data: {
    relationshipType: RelationshipType;
    dependencyWeight: number;
  };
}

export interface NetworkGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export type NetworkGraphData = NetworkGraphResponse;
