import React, { useState, useEffect } from "react";
import { Plus, RefreshCw, Trash2, ArrowRight, Layers, AlertCircle, Network } from "lucide-react";
import { apiClient } from "../api/client";
import { BusinessEntity, BusinessRelationship, EntityType, CriticalityLevel, RelationshipType, NetworkGraphData } from "../types/entity";
import { NetworkGraph } from "../components/NetworkGraph";
import { ImpactPanel } from "../components/network/ImpactPanel";
import { RiskBadge } from "../components/common/Badge";

export const NetworkPage: React.FC = () => {
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [relationships, setRelationships] = useState<BusinessRelationship[]>([]);
  const [graphData, setGraphData] = useState<NetworkGraphData>({ nodes: [], edges: [] });
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Entity state for downstream preview
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [downstreamEntities, setDownstreamEntities] = useState<BusinessEntity[]>([]);

  // Form modals state
  const [showAddEntityModal, setShowAddEntityModal] = useState<boolean>(false);
  const [showAddRelModal, setShowAddRelModal] = useState<boolean>(false);

  // New Entity Form State
  const [newEntity, setNewEntity] = useState({
    name: "",
    type: "supplier" as EntityType,
    location: "",
    criticality: "medium" as CriticalityLevel,
    lead_time_days: 7,
    alternative_supplier_available: false,
  });

  // New Relationship Form State
  const [newRel, setNewRel] = useState({
    source_id: "",
    target_id: "",
    relationship_type: "supplies" as RelationshipType,
    dependency_weight: 0.8,
  });

  const loadNetworkData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [ents, rels, graph] = await Promise.all([
        apiClient.listEntities(),
        apiClient.listRelationships(),
        apiClient.getNetworkGraph(),
      ]);
      setEntities(ents);
      setRelationships(rels);
      setGraphData(graph);
    } catch (err: any) {
      setError(err.message || "Failed to connect to backend server.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadNetworkData();
  }, []);

  const handleEntitySelect = async (entityId: string) => {
    setSelectedEntityId(entityId);
    try {
      const downstream = await apiClient.getDownstreamEntities(entityId, 3);
      setDownstreamEntities(downstream);
    } catch (err) {
      console.error("Failed to fetch downstream entities", err);
    }
  };

  const handleCreateEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiClient.createEntity({
        name: newEntity.name,
        type: newEntity.type,
        location: newEntity.location,
        criticality: newEntity.criticality,
        status: "active",
        metadata: {
          lead_time_days: newEntity.lead_time_days,
          alternative_supplier_available: newEntity.alternative_supplier_available,
        },
      });
      setShowAddEntityModal(false);
      setNewEntity({
        name: "",
        type: "supplier",
        location: "",
        criticality: "medium",
        lead_time_days: 7,
        alternative_supplier_available: false,
      });
      await loadNetworkData();
    } catch (err: any) {
      alert(err.message || "Failed to create entity");
    }
  };

  const handleCreateRelationship = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRel.source_id || !newRel.target_id) {
      alert("Please select both dependent entity and supplier entity.");
      return;
    }
    try {
      await apiClient.createRelationship(newRel);
      setShowAddRelModal(false);
      setNewRel({
        source_id: "",
        target_id: "",
        relationship_type: "supplies",
        dependency_weight: 0.8,
      });
      await loadNetworkData();
    } catch (err: any) {
      alert(err.message || "Failed to create relationship");
    }
  };

  const handleDeleteEntity = async (id: string) => {
    if (!confirm("Delete this entity and all its relationships?")) return;
    try {
      await apiClient.deleteEntity(id);
      if (selectedEntityId === id) setSelectedEntityId(null);
      await loadNetworkData();
    } catch (err: any) {
      alert(err.message || "Failed to delete entity");
    }
  };

  const handleDeleteRel = async (id: string) => {
    try {
      await apiClient.deleteRelationship(id);
      await loadNetworkData();
    } catch (err: any) {
      alert(err.message || "Failed to delete relationship");
    }
  };

  const selectedEntity = entities.find((e) => e.id === selectedEntityId) || null;

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="text-[11px] font-mono uppercase text-[#747686]">
            Graph Infrastructure
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#131316] flex items-center gap-2 mt-0.5">
            <Network className="w-5 h-5 text-[#6c47ff]" />
            <span>Business Network Topology</span>
          </h1>
          <p className="text-xs text-[#5e5f6e] mt-1">
            Map suppliers, factories, warehouses, routes & customers and configure weighted dependency links.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={loadNetworkData}
            disabled={loading}
            className="btn-secondary"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>
          <button
            onClick={() => setShowAddEntityModal(true)}
            className="btn-primary"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Add Entity</span>
          </button>
          <button
            onClick={() => setShowAddRelModal(true)}
            disabled={entities.length < 2}
            className="btn-secondary"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Connect Link</span>
          </button>
        </div>
      </div>

      {/* Error State Banner */}
      {error && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-start gap-3 text-rose-800 text-xs">
          <AlertCircle className="w-4 h-4 text-rose-600 mt-0.5 shrink-0" />
          <div>
            <div className="font-semibold">Network API Error</div>
            <div className="mt-0.5">{error}</div>
          </div>
        </div>
      )}

      {/* Main Layout Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Network Graph Visualizer (2 Cols) */}
        <div className="lg:col-span-2 flex flex-col space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold font-mono text-[#5e5f6e]">
              TOPOLOGY CANVAS ({graphData.nodes.length} Nodes, {graphData.edges.length} Dependency Edges)
            </span>
            <span className="text-[#747686]">
              Click any node to inspect downstream dependencies
            </span>
          </div>

          <div className="h-[600px] w-full relative">
            <NetworkGraph
              graphData={graphData}
              onNodeClick={handleEntitySelect}
              selectedNodeId={selectedEntityId}
              highlightedEntityIds={
                selectedEntityId
                  ? [selectedEntityId, ...downstreamEntities.map((e) => e.id)]
                  : []
              }
            />
          </div>
        </div>

        {/* Sidebar / Impact Inspector Panel (1 Col) */}
        <div className="space-y-6">
          <ImpactPanel
            selectedEntity={selectedEntity}
            downstreamEntities={downstreamEntities}
            onDelete={handleDeleteEntity}
            onClose={() => setSelectedEntityId(null)}
          />

          {/* Relationships Manager Table */}
          <div className="p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
              <h3 className="font-bold text-[#131316] text-xs uppercase tracking-wider font-mono">
                Dependency Links ({relationships.length})
              </h3>
            </div>

            {relationships.length === 0 ? (
              <div className="text-xs text-[#747686] italic py-4 text-center">
                No dependency relationships configured yet.
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto pr-1">
                {relationships.map((rel) => {
                  const source = entities.find((e) => e.id === rel.source_id);
                  const target = entities.find((e) => e.id === rel.target_id);
                  return (
                    <div
                      key={rel.id}
                      className="text-xs bg-[#f7f7f8] p-2.5 rounded-lg border border-[#eeeef0] flex items-center justify-between gap-2"
                    >
                      <div className="truncate">
                        <span className="font-semibold text-[#131316]">{source?.name || rel.source_id}</span>
                        <span className="text-[#747686] mx-1">→ [{rel.relationship_type}] →</span>
                        <span className="font-semibold text-[#6c47ff]">{target?.name || rel.target_id}</span>
                        <span className="ml-2 font-mono text-[10px] text-amber-700 font-bold">
                          {(rel.dependency_weight * 100).toFixed(0)}%
                        </span>
                      </div>
                      <button
                        onClick={() => handleDeleteRel(rel.id)}
                        className="text-[#747686] hover:text-rose-600 p-1 transition-colors"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Entity Table View */}
      <div className="p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
          <h3 className="font-bold text-[#131316] text-sm">
            Monitored Network Entities ({entities.length})
          </h3>
        </div>

        {entities.length === 0 ? (
          <div className="py-8 text-center text-[#747686] text-xs">
            No entities configured. Click <strong className="text-[#131316]">Add Entity</strong> to map your supply chain network.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#f7f7f8] text-[#5e5f6e] uppercase text-[10px] font-mono border-b border-[#d9d9de]">
                <tr>
                  <th className="py-3 px-4 font-semibold">Name</th>
                  <th className="py-3 px-3 font-semibold">Type</th>
                  <th className="py-3 px-3 font-semibold">Location</th>
                  <th className="py-3 px-3 font-semibold">Criticality</th>
                  <th className="py-3 px-3 font-semibold">Lead Time</th>
                  <th className="py-3 px-3 font-semibold">Alt Supplier</th>
                  <th className="py-3 px-4 font-semibold text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eeeef0]">
                {entities.map((ent) => (
                  <tr key={ent.id} className="hover:bg-[#f7f7f8] transition-colors">
                    <td className="py-3 px-4 font-semibold text-[#131316]">{ent.name}</td>
                    <td className="py-3 px-3 capitalize text-[#5e5f6e]">{ent.type}</td>
                    <td className="py-3 px-3 text-[#5e5f6e]">{ent.location}</td>
                    <td className="py-3 px-3">
                      <RiskBadge level={ent.criticality} />
                    </td>
                    <td className="py-3 px-3 text-[#5e5f6e]">{ent.metadata?.lead_time_days ?? "—"} days</td>
                    <td className="py-3 px-3">
                      {ent.metadata?.alternative_supplier_available ? (
                        <span className="text-emerald-700 font-medium">Available</span>
                      ) : (
                        <span className="text-amber-700 font-medium">Sole Source</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => handleDeleteEntity(ent.id)}
                        className="text-[#747686] hover:text-rose-600 transition-colors p-1"
                        title="Delete Entity"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add Entity Modal */}
      {showAddEntityModal && (
        <div className="fixed inset-0 bg-[#131316]/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#d9d9de] rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <h2 className="text-base font-bold text-[#131316]">Add Business Entity</h2>
            <form onSubmit={handleCreateEntity} className="space-y-4 text-xs">
              <div>
                <label className="block text-[#5e5f6e] mb-1 font-medium">Entity Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Taiwan Semiconductor Corp"
                  value={newEntity.name}
                  onChange={(e) => setNewEntity({ ...newEntity, name: e.target.value })}
                  className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[#5e5f6e] mb-1 font-medium">Entity Type</label>
                  <select
                    value={newEntity.type}
                    onChange={(e) => setNewEntity({ ...newEntity, type: e.target.value as EntityType })}
                    className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff] capitalize"
                  >
                    <option value="supplier">Supplier</option>
                    <option value="factory">Factory</option>
                    <option value="warehouse">Warehouse</option>
                    <option value="route">Route</option>
                    <option value="customer">Customer</option>
                  </select>
                </div>

                <div>
                  <label className="block text-[#5e5f6e] mb-1 font-medium">Criticality</label>
                  <select
                    value={newEntity.criticality}
                    onChange={(e) => setNewEntity({ ...newEntity, criticality: e.target.value as CriticalityLevel })}
                    className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff] capitalize"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-[#5e5f6e] mb-1 font-medium">Geographic Location</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Hsinchu, Taiwan"
                  value={newEntity.location}
                  onChange={(e) => setNewEntity({ ...newEntity, location: e.target.value })}
                  className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3 items-center">
                <div>
                  <label className="block text-[#5e5f6e] mb-1 font-medium">Lead Time (Days)</label>
                  <input
                    type="number"
                    min="0"
                    value={newEntity.lead_time_days}
                    onChange={(e) => setNewEntity({ ...newEntity, lead_time_days: parseInt(e.target.value) || 0 })}
                    className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                  />
                </div>

                <div className="flex items-center gap-2 pt-4">
                  <input
                    type="checkbox"
                    id="altSupplier"
                    checked={newEntity.alternative_supplier_available}
                    onChange={(e) => setNewEntity({ ...newEntity, alternative_supplier_available: e.target.checked })}
                    className="w-4 h-4 rounded accent-[#6c47ff]"
                  />
                  <label htmlFor="altSupplier" className="text-[#131316] select-none font-medium">
                    Alt Supplier Available
                  </label>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#eeeef0]">
                <button
                  type="button"
                  onClick={() => setShowAddEntityModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Save Entity
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Relationship Modal */}
      {showAddRelModal && (
        <div className="fixed inset-0 bg-[#131316]/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white border border-[#d9d9de] rounded-2xl w-full max-w-lg p-6 space-y-4 shadow-2xl">
            <h2 className="text-base font-bold text-[#131316]">Connect Dependency Link</h2>
            <form onSubmit={handleCreateRelationship} className="space-y-4 text-xs">
              <div>
                <label className="block text-[#5e5f6e] mb-1 font-medium">Dependent Entity (Downstream Node)</label>
                <select
                  value={newRel.source_id}
                  onChange={(e) => setNewRel({ ...newRel, source_id: e.target.value })}
                  required
                  className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                >
                  <option value="">Select dependent entity...</option>
                  {entities.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name} ({e.type})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-[#5e5f6e] mb-1 font-medium">Supplier / Upstream Facility (Target Node)</label>
                <select
                  value={newRel.target_id}
                  onChange={(e) => setNewRel({ ...newRel, target_id: e.target.value })}
                  required
                  className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                >
                  <option value="">Select supplier entity...</option>
                  {entities
                    .filter((e) => e.id !== newRel.source_id)
                    .map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.name} ({e.type})
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="block text-[#5e5f6e] mb-1 font-medium">Relationship Type</label>
                <select
                  value={newRel.relationship_type}
                  onChange={(e) => setNewRel({ ...newRel, relationship_type: e.target.value as RelationshipType })}
                  className="w-full bg-white border border-[#d9d9de] rounded-lg px-3 py-2 text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                >
                  <option value="supplies">supplies</option>
                  <option value="ships_to">ships_to</option>
                  <option value="stores_at">stores_at</option>
                  <option value="depends_on">depends_on</option>
                </select>
              </div>

              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-[#5e5f6e] font-medium">Dependency Weight</label>
                  <span className="font-mono text-[#6c47ff] font-bold">
                    {(newRel.dependency_weight * 100).toFixed(0)}%
                  </span>
                </div>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.05"
                  value={newRel.dependency_weight}
                  onChange={(e) => setNewRel({ ...newRel, dependency_weight: parseFloat(e.target.value) })}
                  className="w-full accent-[#6c47ff]"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#eeeef0]">
                <button
                  type="button"
                  onClick={() => setShowAddRelModal(false)}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                >
                  Connect Link
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
