import React from 'react';
import { ConfidenceLabel } from '../../types/events';
import { RiskLevel } from '../../types/risk';

interface RiskBadgeProps {
  level?: RiskLevel | string;
  className?: string;
}

export const RiskBadge: React.FC<RiskBadgeProps> = ({ level, className = '' }) => {
  const norm = (level || 'low').toLowerCase();

  if (norm === 'critical') {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-mono font-bold uppercase tracking-wider bg-red-950 text-red-300 border border-red-800 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-ping" />
        Critical
      </span>
    );
  }

  if (norm === 'high') {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-semibold uppercase tracking-wider bg-rose-50 text-rose-700 border border-rose-200 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
        High
      </span>
    );
  }

  if (norm === 'medium') {
    return (
      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-medium uppercase tracking-wider bg-amber-50 text-amber-700 border border-amber-200 ${className}`}>
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        Medium
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-mono font-medium uppercase tracking-wider bg-emerald-50 text-emerald-700 border border-emerald-200 ${className}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
      Low
    </span>
  );
};

interface VerificationBadgeProps {
  status?: ConfidenceLabel | string;
  isGated?: boolean;
  score?: number;
  className?: string;
}

export const VerificationBadge: React.FC<VerificationBadgeProps> = ({
  status,
  isGated,
  score,
  className = '',
}) => {
  const norm = (status || 'unconfirmed').toLowerCase();

  // HIGH: subtle positive treatment
  if (norm === 'high') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold tracking-wide bg-emerald-50 text-emerald-800 border border-emerald-200 ${className}`}
        title={`Credibility score: ${score ? score.toFixed(1) : '80+'}/100. High credibility evidence.`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
        HIGH VERIFIED
      </span>
    );
  }

  // MODERATE: neutral / electric violet treatment
  if (norm === 'moderate') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold tracking-wide bg-[#f5f3ff] text-[#5b21b6] border border-[#ddd6fe] ${className}`}
        title={`Credibility score: ${score ? score.toFixed(1) : '60-79'}/100. Credible source, moderate corroboration.`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-[#6c47ff]" />
        MODERATE VERIFIED
      </span>
    );
  }

  // LOW: warm amber treatment
  if (norm === 'low') {
    return (
      <span
        className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold tracking-wide bg-amber-50 text-amber-800 border border-amber-200 ${className}`}
        title={`Credibility score: ${score ? score.toFixed(1) : '35-59'}/100. Limited corroboration.`}
      >
        <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
        LOW CONFIDENCE
      </span>
    );
  }

  // UNCONFIRMED: muted amber / warning (Needs Review, NOT "Fake")
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold tracking-wide bg-amber-50/80 text-amber-900 border border-amber-300 ${className}`}
      title={isGated ? "Score < 35: Gated by verification engine. Retained for review." : "Awaiting verification"}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-amber-600 animate-pulse" />
      UNCONFIRMED {isGated ? '· GATED' : ''}
    </span>
  );
};
