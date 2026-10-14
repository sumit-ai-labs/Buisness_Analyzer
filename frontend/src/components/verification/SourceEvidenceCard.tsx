import React from 'react';
import { ExternalLink, Globe, Shield, Calendar, GitFork } from 'lucide-react';
import { CredibilityAssessment } from '../../types/events';

interface SourceEvidenceCardProps {
  sourceUrl?: string;
  assessment?: CredibilityAssessment | null;
  retrievedAt?: string;
  className?: string;
}

export const SourceEvidenceCard: React.FC<SourceEvidenceCardProps> = ({
  sourceUrl,
  assessment,
  retrievedAt,
  className = '',
}) => {
  let hostname = 'External Source';
  if (sourceUrl) {
    try {
      hostname = new URL(sourceUrl).hostname.replace('www.', '');
    } catch {
      hostname = assessment?.source_domain || 'External Source';
    }
  } else if (assessment?.source_domain) {
    hostname = assessment.source_domain;
  }

  const isVerifiedDomain = (assessment?.source_reputation_score ?? 50) >= 70;
  const corroborationCount = assessment?.corroborating_source_count ?? 0;

  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl space-y-4 shadow-sm ${className}`}>
      <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-[#6c47ff]" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-[#131316]">
            Source Evidence & Attribution
          </h4>
        </div>
        {sourceUrl && (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-[#6c47ff] hover:text-[#615cf6] font-medium flex items-center gap-1 transition-colors"
          >
            <span>Open Source</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] block">Publisher Domain</span>
          <span className="font-semibold text-[#131316] font-mono truncate block mt-0.5" title={hostname}>
            {hostname}
          </span>
          <span className="text-[10px] text-[#5e5f6e] mt-1 block">
            {isVerifiedDomain ? 'Verified Tier Registry' : 'Unverified Domain (Heuristic)'}
          </span>
        </div>

        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] block">Domain Reputation</span>
          <div className="flex items-baseline gap-1 mt-0.5">
            <span className="font-bold text-base font-mono text-[#131316]">
              {assessment?.source_reputation_score ?? 50}
            </span>
            <span className="text-[11px] text-[#747686]">/ 100</span>
          </div>
          <span className="text-[10px] font-mono text-[#6c47ff] mt-1 block capitalize">
            {assessment?.source_tier || 'Standard Tier'}
          </span>
        </div>

        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] flex items-center gap-1">
            <GitFork className="w-3 h-3 text-[#747686]" /> Corroborating Sources
          </span>
          <span className="font-bold text-base font-mono text-[#131316] block mt-0.5">
            {corroborationCount}
          </span>
          <span className="text-[10px] text-[#5e5f6e] mt-1 block">
            {corroborationCount > 0 ? 'Cross-verified event' : 'Single source report'}
          </span>
        </div>

        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
          <span className="text-[#747686] text-[11px] flex items-center gap-1">
            <Calendar className="w-3 h-3 text-[#747686]" /> Ingestion Timestamp
          </span>
          <span className="font-medium text-xs text-[#131316] block mt-1">
            {retrievedAt ? new Date(retrievedAt).toLocaleDateString() : 'Real-time scan'}
          </span>
          <span className="text-[10px] text-[#747686]">
            {retrievedAt ? new Date(retrievedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Recent'}
          </span>
        </div>
      </div>
    </div>
  );
};
