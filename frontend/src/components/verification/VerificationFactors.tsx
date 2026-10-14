import React from 'react';
import { CredibilityAssessment } from '../../types/events';
import { Globe, GitFork, Sparkles, BrainCircuit } from 'lucide-react';

interface VerificationFactorsProps {
  assessment?: CredibilityAssessment | null;
  className?: string;
}

export const VerificationFactors: React.FC<VerificationFactorsProps> = ({
  assessment,
  className = '',
}) => {
  if (!assessment) {
    return (
      <div className={`p-4 bg-white border border-[#d9d9de] rounded-2xl text-xs text-[#747686] ${className}`}>
        No detailed credibility factors available for this item.
      </div>
    );
  }

  const {
    source_domain,
    source_tier,
    source_reputation_score,
    corroborating_source_count,
    content_style_score,
    llm_extraction_confidence,
    factors = {},
  } = assessment;

  // Corroboration score normalized: 0 sources = 0, 1 = 50, 2+ = 100
  const corroborationScore = Math.min(100, corroborating_source_count * 50);

  const factorList = [
    {
      label: 'Source Reputation',
      icon: Globe,
      value: source_reputation_score,
      subtext: `${source_domain || 'Unknown'} · ${source_tier || 'Tier 3'}`,
      weight: '35% weight',
      description: 'Domain credibility tier based on established news, logistics, and governmental sources registry.',
    },
    {
      label: 'Corroboration',
      icon: GitFork,
      value: corroborationScore,
      subtext: `${corroborating_source_count} corroborating source${corroborating_source_count === 1 ? '' : 's'}`,
      weight: '25% weight',
      description: 'Cross-verification by independent media reporting the same disruption event.',
    },
    {
      label: 'ML Content Style',
      icon: Sparkles,
      value: content_style_score,
      subtext: 'TF-IDF Logistic Classifier v1.0',
      weight: '20% weight',
      description: 'Analyzes clickbait linguistic patterns, sensational tone, and factual syntactic structure.',
    },
    {
      label: 'LLM Extraction Confidence',
      icon: BrainCircuit,
      value: llm_extraction_confidence,
      subtext: `${Math.round(llm_extraction_confidence)}% certainty`,
      weight: '20% weight',
      description: 'Extraction clarity of disruption entities, dates, locations, and severities from raw text.',
    },
  ];

  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl space-y-4 shadow-sm ${className}`}>
      <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider text-[#131316]">
            Evidence Verification Breakdown
          </h4>
          <p className="text-[11px] text-[#747686]">Deterministic 4-factor authenticity model</p>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#f7f7f8] border border-[#d9d9de] text-[#5e5f6e]">
          v{assessment.model_version || '1.0'}
        </span>
      </div>

      <div className="space-y-3.5">
        {factorList.map((f) => {
          const Icon = f.icon;
          const scoreVal = Math.round(f.value || 0);

          return (
            <div key={f.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5 font-medium text-[#131316]">
                  <Icon className="w-3.5 h-3.5 text-[#6c47ff]" />
                  <span>{f.label}</span>
                </div>
                <div className="flex items-center gap-2 font-mono">
                  <span className="text-[11px] text-[#747686]">{f.subtext}</span>
                  <span className="font-bold text-[#131316] w-8 text-right">{scoreVal}</span>
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-[#eeeef0] rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-[#6c47ff] h-full rounded-full transition-all duration-300"
                  style={{ width: `${Math.min(100, Math.max(0, scoreVal))}%` }}
                />
              </div>

              <div className="flex justify-between text-[10px] text-[#747686] pt-0.5">
                <span>{f.description}</span>
                <span className="font-mono text-[#5e5f6e]">{f.weight}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Raw Factor Points Summary if available */}
      {Object.keys(factors).length > 0 && (
        <div className="pt-2 border-t border-[#eeeef0] flex flex-wrap gap-2 text-[10px] font-mono text-[#5e5f6e]">
          {Object.entries(factors).map(([k, v]) => (
            <span key={k} className="px-2 py-0.5 rounded bg-[#f7f7f8] border border-[#d9d9de]">
              {k.replace(/_/g, ' ')}: <strong className="text-[#131316]">{typeof v === 'number' ? v.toFixed(1) : v}</strong>
            </span>
          ))}
        </div>
      )}
    </div>
  );
};
