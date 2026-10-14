import React, { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Node,
  Edge,
  Handle,
  Position,
  NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import { Anchor, Factory, Navigation, Truck, Users, Warehouse } from "lucide-react";
import { NetworkGraphData } from '../types/entity';
import { NetworkLegend } from './network/NetworkLegend';

interface NetworkGraphProps {
  graphData: NetworkGraphData;
  onNodeClick?: (nodeId: string) => void;
  selectedNodeId?: string | null;
  highlightedEntityIds?: string[];
}

const getIconForType = (type: string) => {
  switch (type) {
    case "supplier":
      return <Anchor className="w-4 h-4 text-[#6c47ff]" />;
    case "factory":
      return <Factory className="w-4 h-4 text-[#5e5f6e]" />;
    case "warehouse":
      return <Warehouse className="w-4 h-4 text-[#747686]" />;
    case "route":
      return <Navigation className="w-4 h-4 text-blue-600" />;
    case "customer":
      return <Users className="w-4 h-4 text-emerald-700" />;
    default:
      return <Truck className="w-4 h-4 text-[#5e5f6e]" />;
  }
};

const CustomEntityNode: React.FC<NodeProps> = ({ data, selected }) => {
  const nodeData = data as any;
  const isHighlighted = nodeData.isHighlighted;
  const criticality = nodeData.criticality;

  // Operational styling: Normal is clean white card.
  // Affected/High has subtle violet/amber accent.
  // Critical has red emphasis.
  let borderStyle = "border-[#d9d9de]";
  let statusBadge = "bg-[#f7f7f8] text-[#5e5f6e] border-[#d9d9de]";

  if (criticality === "high") {
    borderStyle = "border-rose-400 shadow-sm";
    statusBadge = "bg-rose-50 text-rose-800 border-rose-200";
  } else if (criticality === "medium") {
    borderStyle = "border-amber-300";
    statusBadge = "bg-amber-50 text-amber-800 border-amber-200";
  }

  if (isHighlighted) {
    borderStyle = "border-[#6c47ff] shadow-md ring-2 ring-[#6c47ff]/20";
  } else if (selected) {
    borderStyle = "border-[#6c47ff] ring-2 ring-[#6c47ff]/30 shadow-md";
  }

  return (
    <div
      className={`px-3.5 py-3 rounded-xl border bg-white shadow-sm transition-all duration-200 min-w-[190px] ${borderStyle} ${
        selected ? "scale-105" : ""
      }`}
    >
      <Handle type="target" position={Position.Top} className="!bg-[#6c47ff] !w-2.5 !h-2.5" />

      <div className="flex items-center space-x-2.5 mb-1.5">
        <div className="p-1.5 rounded-md bg-[#f7f7f8] border border-[#d9d9de]">
          {getIconForType(nodeData.entityType)}
        </div>
        <div className="overflow-hidden">
          <h4 className="text-xs font-bold text-[#131316] truncate max-w-[125px]">{nodeData.label}</h4>
          <p className="text-[10px] text-[#747686] truncate max-w-[125px]">{nodeData.location}</p>
        </div>
      </div>

      <div className="flex items-center justify-between text-[10px] pt-1.5 border-t border-[#eeeef0] mt-1">
        <span className="capitalize font-medium text-[#5e5f6e]">{nodeData.entityType}</span>
        <span className={`uppercase font-mono font-semibold tracking-wider text-[9px] px-1.5 py-0.2 rounded border ${statusBadge}`}>
          {nodeData.criticality}
        </span>
      </div>

      <Handle type="source" position={Position.Bottom} className="!bg-[#6c47ff] !w-2.5 !h-2.5" />
    </div>
  );
};

const nodeTypes = {
  customEntityNode: CustomEntityNode,
};

export const NetworkGraph: React.FC<NetworkGraphProps> = ({
  graphData,
  onNodeClick,
  selectedNodeId,
  highlightedEntityIds = [],
}) => {
  const { nodes, edges } = useMemo(() => {
    const nodeCount = graphData.nodes.length;
    const columns = Math.ceil(Math.sqrt(nodeCount)) || 1;
    const spacingX = 250;
    const spacingY = 160;

    const formattedNodes: Node[] = graphData.nodes.map((node: any, index: number) => {
      const col = index % columns;
      const row = Math.floor(index / columns);

      return {
        id: node.id,
        type: "customEntityNode",
        position: node.position || { x: col * spacingX + 60, y: row * spacingY + 60 },
        data: {
          ...node.data,
          isHighlighted: highlightedEntityIds.includes(node.id),
        },
        selected: selectedNodeId === node.id,
      };
    });

    const formattedEdges: Edge[] = graphData.edges.map((edge: any) => {
      const isHighlightedEdge =
        highlightedEntityIds.includes(edge.source) && highlightedEntityIds.includes(edge.target);

      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
        type: "smoothstep",
        animated: isHighlightedEdge || (edge.data?.dependencyWeight || 0) > 0.7,
        style: {
          stroke: isHighlightedEdge ? "#6c47ff" : "#9394a1",
          strokeWidth: Math.max(1.5, (edge.data?.dependencyWeight || 0.5) * 2.5),
        },
        labelStyle: { fill: "#5e5f6e", fontSize: 10, fontWeight: 500, fontFamily: 'monospace' },
        labelBgStyle: { fill: "#ffffff", rx: 3, ry: 3, stroke: "#d9d9de", strokeWidth: 1 },
      };
    });

    return { nodes: formattedNodes, edges: formattedEdges };
  }, [graphData, selectedNodeId, highlightedEntityIds]);

  return (
    <div className="w-full h-[600px] rounded-2xl bg-[#f7f7f8] border border-[#d9d9de] overflow-hidden relative shadow-sm">
      {/* Floating Legend */}
      <div className="absolute top-4 left-4 z-10">
        <NetworkLegend />
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={(_, node) => onNodeClick && onNodeClick(node.id)}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        className="bg-[#f7f7f8]"
      >
        <Background color="#d9d9de" gap={20} size={1} />
        <Controls className="!bg-white !border-[#d9d9de] !fill-[#5e5f6e] !shadow-sm !rounded-lg" />
        <MiniMap
          nodeColor={(node) => {
            const criticality = (node.data as any)?.criticality;
            if (criticality === "high") return "#e5484d";
            if (criticality === "medium") return "#f59e0b";
            return "#10b981";
          }}
          className="!bg-white !border-[#d9d9de] rounded-xl !shadow-sm"
        />
      </ReactFlow>
    </div>
  );
};
