import React from 'react';
import { DisruptionEvent, CredibilityAssessment } from '../../types/events';
import { RiskBadge, VerificationBadge } from '../common/Badge';
import { ExternalLink, Eye, AlertCircle } from 'lucide-react';

interface IncidentTableProps {
  events: DisruptionEvent[];
  credibilityMap?: Record<string, CredibilityAssessment>;
  onSelectEvent: (event: DisruptionEvent) => void;
  loading?: boolean;
}

export const IncidentTable: React.FC<IncidentTableProps> = ({
  events,
  credibilityMap = {},
  onSelectEvent,
  loading = false,
}) => {
  if (loading) {
    return (
      <div className="p-8 text-center text-xs text-[#747686] animate-pulse">
        Retrieving disruption events and credibility evidence...
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="py-10 text-center text-xs text-[#747686] space-y-1">
        <p className="font-semibold text-[#131316]">No disruption events recorded</p>
        <p>Trigger a monitoring cycle to scan external intelligence channels.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs">
        <thead className="bg-[#f7f7f8] text-[#5e5f6e] uppercase text-[10px] font-mono border-b border-[#d9d9de]">
          <tr>
            <th className="py-3 px-4 font-semibold">Event</th>
            <th className="py-3 px-3 font-semibold">Type</th>
            <th className="py-3 px-3 font-semibold">Source</th>
            <th className="py-3 px-3 font-semibold">Credibility</th>
            <th className="py-3 px-3 font-semibold">Severity</th>
            <th className="py-3 px-3 font-semibold">Risk Score</th>
            <th className="py-3 px-3 font-semibold">Time</th>
            <th className="py-3 px-4 font-semibold text-right">Action</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[#eeeef0]">
          {events.map((evt) => {
            const assessment = evt.credibility || (evt.credibility_assessment_id ? credibilityMap[evt.credibility_assessment_id] : null);
            const score = assessment?.authenticity_score ?? 63.5;
            const status = assessment?.confidence_label ?? 'moderate';
            const isGated = assessment?.is_gated ?? false;

            let sourceHostname = 'External';
            if (evt.source_url) {
              try {
                sourceHostname = new URL(evt.source_url).hostname.replace('www.', '');
              } catch {
                sourceHostname = assessment?.source_domain || 'News Source';
              }
            } else if (assessment?.source_domain) {
              sourceHostname = assessment.source_domain;
            }

            return (
              <tr
                key={evt.id}
                onClick={() => onSelectEvent(evt)}
                className="hover:bg-[#f7f7f8] cursor-pointer transition-colors group"
              >
                {/* Event Headline & Location */}
                <td className="py-3 px-4 max-w-xs">
                  <div className="font-semibold text-[#131316] truncate group-hover:text-[#6c47ff] transition-colors" title={evt.headline}>
                    {evt.headline || 'Disruption Incident'}
                  </div>
                  <div className="text-[11px] text-[#747686] truncate">
                    {evt.location_mentioned ? `Location: ${evt.location_mentioned}` : 'Regional supply route'}
                  </div>
                </td>

                {/* Event Type */}
                <td className="py-3 px-3 capitalize text-[#5e5f6e] font-medium">
                  {evt.event_type}
                </td>

                {/* Source Attribution */}
                <td className="py-3 px-3 text-[#5e5f6e]">
                  <span className="font-mono text-[11px] block truncate max-w-[120px]" title={sourceHostname}>
                    {sourceHostname}
                  </span>
                  <span className="text-[10px] text-[#747686]">
                    {assessment?.source_tier || 'Tier 2'}
                  </span>
                </td>

                {/* Credibility Badge (Centerpiece) */}
                <td className="py-3 px-3">
                  <VerificationBadge
                    status={status}
                    isGated={isGated}
                    score={score}
                  />
                  <div className="text-[10px] font-mono text-[#747686] mt-0.5">
                    Score {score.toFixed(1)}
                  </div>
                </td>

                {/* Raw Severity */}
                <td className="py-3 px-3">
                  <RiskBadge level={evt.severity_raw === 'high' ? 'high' : evt.severity_raw === 'medium' ? 'medium' : 'low'} />
                </td>

                {/* Risk Score */}
                <td className="py-3 px-3">
                  <span className="font-mono font-bold text-xs text-[#131316]">
                    {Math.round((score * 0.5) + (evt.confidence * 50))} / 100
                  </span>
                </td>

                {/* Time */}
                <td className="py-3 px-3 text-[11px] text-[#747686] whitespace-nowrap">
                  {evt.retrieved_at ? new Date(evt.retrieved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '2m ago'}
                </td>

                {/* Action button */}
                <td className="py-3 px-4 text-right">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectEvent(evt);
                    }}
                    className="p-1.5 rounded-md hover:bg-[#eeeef0] text-[#747686] hover:text-[#131316] transition-colors inline-flex items-center gap-1 text-[11px] font-medium"
                  >
                    <Eye className="w-3.5 h-3.5" />
                    <span>View →</span>
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
