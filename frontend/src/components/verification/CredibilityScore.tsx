import React from 'react';
import { CredibilityAssessment } from '../../types/events';
import { VerificationBadge } from '../common/Badge';
import { ShieldCheck, ShieldAlert, Info } from 'lucide-react';

interface CredibilityScoreProps {
  assessment?: CredibilityAssessment | null;
  score?: number;
  label?: string;
  isGated?: boolean;
  compact?: boolean;
}

export const CredibilityScore: React.FC<CredibilityScoreProps> = ({
  assessment,
  score: propScore,
  label: propLabel,
  isGated: propIsGated,
  compact = false,
}) => {
  const score = assessment?.authenticity_score ?? propScore ?? 0;
  const label = assessment?.confidence_label ?? propLabel ?? (score < 35 ? 'unconfirmed' : score < 60 ? 'low' : score < 80 ? 'moderate' : 'high');
  const isGated = assessment?.is_gated ?? propIsGated ?? (score < 35);

  const percentage = Math.min(100, Math.max(0, score));

  // Determine meter fill color
  const getMeterColor = () => {
    if (label === 'high') return 'bg-emerald-600';
    if (label === 'moderate') return 'bg-[#6c47ff]';
    if (label === 'low') return 'bg-amber-500';
    return 'bg-amber-600';
  };

  return (
    <div className={`space-y-3 ${compact ? '' : 'p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm'}`}>
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[11px] font-mono uppercase tracking-wider text-[#747686] block">
            Credibility Verification
          </span>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="text-2xl font-bold font-mono text-[#131316]">
              {score.toFixed(1)}
            </span>
            <span className="text-xs text-[#747686]">/ 100</span>
          </div>
        </div>

        <div>
          <VerificationBadge status={label} isGated={isGated} score={score} />
        </div>
      </div>

      {/* Segmented Credibility Scale */}
      <div className="space-y-1.5 pt-1">
        <div className="relative h-2.5 bg-[#eeeef0] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${getMeterColor()}`}
            style={{ width: `${percentage}%` }}
          />
          {/* Threshold markers */}
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-red-400 opacity-60"
            style={{ left: '35%' }}
            title="Gate Threshold (35): Below this is Unconfirmed"
          />
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-amber-400 opacity-60"
            style={{ left: '60%' }}
            title="Moderate Threshold (60)"
          />
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-emerald-400 opacity-60"
            style={{ left: '80%' }}
            title="High Confidence Threshold (80)"
          />
        </div>

        {/* Scale labels */}
        <div className="flex justify-between text-[10px] font-mono text-[#747686]">
          <span>0 (Gated &lt; 35)</span>
          <span className="text-amber-700">35</span>
          <span className="text-[#6c47ff]">60 (Mod)</span>
          <span className="text-emerald-700">80 (High)</span>
          <span>100</span>
        </div>
      </div>

      {/* Gating Status Indicator */}
      <div className="pt-2 border-t border-[#eeeef0] flex items-center justify-between text-xs">
        <div className="flex items-center gap-1.5">
          {isGated ? (
            <>
              <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
              <span className="text-amber-800 font-medium">Gated: Awaiting review (low confidence)</span>
            </>
          ) : (
            <>
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
              <span className="text-emerald-800 font-medium">Verified: Proceeded to impact assessment</span>
            </>
          )}
        </div>

        <div className="text-[11px] text-[#747686] flex items-center gap-1" title="Credibility score is computed from domain reputation, cross-source corroboration, ML content-style features, and LLM extraction confidence.">
          <Info className="w-3 h-3" />
          <span>4-Factor Model</span>
        </div>
      </div>
    </div>
  );
};
