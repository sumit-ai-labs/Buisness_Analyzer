import React from 'react';
import { Check, Loader2 } from 'lucide-react';

interface PipelineStatusProps {
  isRunning?: boolean;
  activeStage?: number; // 0 to 5
  className?: string;
}

const STAGES = [
  { id: 'detect', label: 'DETECT', desc: 'News & external signals' },
  { id: 'understand', label: 'UNDERSTAND', desc: 'LLM entity & event extraction' },
  { id: 'verify', label: 'VERIFY', desc: 'Credibility engine gating' },
  { id: 'connect', label: 'CONNECT', desc: 'Network graph traversal' },
  { id: 'assess', label: 'ASSESS', desc: '5-factor deterministic risk' },
  { id: 'alert', label: 'ALERT', desc: 'Operational early warning' },
];

export const PipelineStatus: React.FC<PipelineStatusProps> = ({
  isRunning = false,
  activeStage = -1,
  className = '',
}) => {
  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm ${className}`}>
      <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3 mb-4">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
            Intelligence Pipeline
          </span>
          <h4 className="text-xs font-bold text-[#131316]">6-Stage Architecture</h4>
        </div>

        <div className="flex items-center gap-1.5 text-[11px] font-mono">
          {isRunning ? (
            <span className="flex items-center gap-1 text-[#6c47ff] font-semibold">
              <Loader2 className="w-3 h-3 animate-spin" /> Running Cycle...
            </span>
          ) : (
            <span className="flex items-center gap-1 text-emerald-700 font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> System Ready
            </span>
          )}
        </div>
      </div>

      {/* Horizontal or Grid Steps */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2">
        {STAGES.map((s, idx) => {
          let statusState: 'pending' | 'active' | 'completed' = 'pending';
          if (isRunning) {
            if (idx < (activeStage >= 0 ? activeStage : 2)) statusState = 'completed';
            else if (idx === (activeStage >= 0 ? activeStage : 2)) statusState = 'active';
            else statusState = 'pending';
          } else {
            statusState = 'completed';
          }

          const isVerify = s.id === 'verify';

          return (
            <div
              key={s.id}
              className={`p-2.5 rounded-xl border text-left transition-all ${
                statusState === 'active'
                  ? 'bg-[#f5f3ff] border-[#6c47ff] shadow-sm'
                  : statusState === 'completed'
                  ? isVerify
                    ? 'bg-[#f5f3ff]/50 border-[#ddd6fe]'
                    : 'bg-[#f7f7f8] border-[#d9d9de]'
                  : 'bg-white border-[#eeeef0] opacity-50'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className={`text-[10px] font-mono font-bold ${
                  isVerify ? 'text-[#6c47ff]' : 'text-[#131316]'
                }`}>
                  {s.label}
                </span>
                {statusState === 'completed' ? (
                  <Check className="w-3 h-3 text-emerald-600" />
                ) : statusState === 'active' ? (
                  <Loader2 className="w-3 h-3 text-[#6c47ff] animate-spin" />
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-[#d9d9de]" />
                )}
              </div>
              <p className="text-[10px] text-[#747686] leading-tight truncate" title={s.desc}>
                {s.desc}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
