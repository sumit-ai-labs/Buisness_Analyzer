import React from 'react';
import { BusinessEntity } from '../../types/entity';
import { ArrowRight, Trash2, ShieldAlert, X } from 'lucide-react';
import { RiskBadge } from '../common/Badge';

interface ImpactPanelProps {
  selectedEntity: BusinessEntity | null;
  downstreamEntities: BusinessEntity[];
  onDelete?: (id: string) => void;
  onClose?: () => void;
  className?: string;
}

export const ImpactPanel: React.FC<ImpactPanelProps> = ({
  selectedEntity,
  downstreamEntities,
  onDelete,
  onClose,
  className = '',
}) => {
  if (!selectedEntity) {
    return (
      <div className={`p-6 bg-white border border-[#d9d9de] border-dashed rounded-2xl text-center text-xs text-[#747686] space-y-2 ${className}`}>
        <p className="font-semibold text-[#131316]">No Network Node Selected</p>
        <p>Click any node in the topology canvas to inspect downstream dependency propagation and risk exposure.</p>
      </div>
    );
  }

  const riskEstimate = selectedEntity.criticality === 'high' ? 84 : selectedEntity.criticality === 'medium' ? 62 : 35;

  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-start justify-between border-b border-[#eeeef0] pb-3">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
            Impact Analysis
          </span>
          <h3 className="font-bold text-[#131316] text-base">{selectedEntity.name}</h3>
          <span className="text-xs text-[#5e5f6e] capitalize">{selectedEntity.type} · {selectedEntity.location}</span>
        </div>

        <div className="flex items-center gap-1">
          {onDelete && (
            <button
              onClick={() => onDelete(selectedEntity.id)}
              className="p-1.5 text-[#747686] hover:text-rose-600 transition-colors"
              title="Delete Entity"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-[#747686] hover:text-[#131316] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] block">Direct Impact</span>
          <div className="mt-1">
            <RiskBadge level={selectedEntity.criticality} />
          </div>
        </div>

        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] block">Downstream Entities</span>
          <span className="font-mono font-bold text-base text-[#131316] block mt-0.5">
            {downstreamEntities.length}
          </span>
        </div>

        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] block">Estimated Exposure</span>
          <span className="font-mono font-bold text-base text-[#6c47ff] block mt-0.5">
            {riskEstimate} <span className="text-[10px] font-normal text-[#747686]">/ 100</span>
          </span>
        </div>

        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] block">Lead Time Buffer</span>
          <span className="font-medium text-xs text-[#131316] block mt-1">
            {selectedEntity.metadata?.lead_time_days ?? 7} days
          </span>
        </div>
      </div>

      {/* Downstream Path View */}
      <div className="space-y-2 pt-2 border-t border-[#eeeef0]">
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-[#131316] flex items-center gap-1.5">
            <ArrowRight className="w-3.5 h-3.5 text-[#6c47ff]" />
            Downstream Dependencies ({downstreamEntities.length})
          </span>
        </div>

        {downstreamEntities.length === 0 ? (
          <div className="p-3 rounded-xl bg-[#f7f7f8] text-xs text-[#747686] italic text-center">
            No downstream facilities directly dependent on this node.
          </div>
        ) : (
          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {downstreamEntities.map((d) => (
              <div
                key={d.id}
                className="p-2.5 rounded-lg bg-[#f7f7f8] border border-[#eeeef0] flex items-center justify-between text-xs"
              >
                <div>
                  <span className="font-semibold text-[#131316] block">{d.name}</span>
                  <span className="text-[10px] text-[#747686] capitalize">{d.type} · {d.location}</span>
                </div>
                <RiskBadge level={d.criticality} />
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
