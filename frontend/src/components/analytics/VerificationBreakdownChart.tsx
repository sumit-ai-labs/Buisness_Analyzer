import React from 'react';
import { ShieldCheck, ShieldAlert, AlertCircle, CheckCircle } from 'lucide-react';

interface VerificationBreakdownProps {
  counts?: {
    high: number;
    moderate: number;
    low: number;
    unconfirmed: number;
  };
  className?: string;
}

export const VerificationBreakdownChart: React.FC<VerificationBreakdownProps> = ({
  counts = { high: 0, moderate: 0, low: 0, unconfirmed: 0 },
  className = '',
}) => {
  const sum = counts.high + counts.moderate + counts.low + counts.unconfirmed;
  const total = sum > 0 ? sum : 1;

  const items = [
    {
      label: 'High Confidence',
      count: counts.high,
      percentage: sum > 0 ? Math.round((counts.high / total) * 100) : 0,
      color: 'bg-emerald-600',
      textColor: 'text-emerald-800',
      bgColor: 'bg-emerald-50',
      borderColor: 'border-emerald-200',
      icon: CheckCircle,
      desc: 'Score ≥ 80: High source tier & multi-source verified',
    },
    {
      label: 'Moderate',
      count: counts.moderate,
      percentage: sum > 0 ? Math.round((counts.moderate / total) * 100) : 0,
      color: 'bg-[#6c47ff]',
      textColor: 'text-[#5b21b6]',
      bgColor: 'bg-[#f5f3ff]',
      borderColor: 'border-[#ddd6fe]',
      icon: ShieldCheck,
      desc: 'Score 60–79: Reputable source, moderate corroboration',
    },
    {
      label: 'Low Confidence',
      count: counts.low,
      percentage: sum > 0 ? Math.round((counts.low / total) * 100) : 0,
      color: 'bg-amber-500',
      textColor: 'text-amber-800',
      bgColor: 'bg-amber-50',
      borderColor: 'border-amber-200',
      icon: AlertCircle,
      desc: 'Score 35–59: Passed gate but limited corroboration',
    },
    {
      label: 'Unconfirmed (Gated)',
      count: counts.unconfirmed,
      percentage: sum > 0 ? Math.round((counts.unconfirmed / total) * 100) : 0,
      color: 'bg-amber-600',
      textColor: 'text-amber-900',
      bgColor: 'bg-amber-50/70',
      borderColor: 'border-amber-300',
      icon: ShieldAlert,
      desc: 'Score < 35: Gated by engine, awaiting operator review',
    },
  ];

  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4 ${className}`}>
      <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
            Verification Engine Summary
          </span>
          <h4 className="text-xs font-bold text-[#131316]">Credibility Tiers</h4>
        </div>
        <span className="font-mono text-xs text-[#747686]">
          {total} Total Signals
        </span>
      </div>

      {/* Segmented Bar */}
      <div className="h-3 w-full bg-[#eeeef0] rounded-full overflow-hidden flex gap-0.5">
        {items.map((item) => (
          <div
            key={item.label}
            className={`${item.color} h-full transition-all duration-300`}
            style={{ width: `${item.percentage}%` }}
            title={`${item.label}: ${item.count} (${item.percentage}%)`}
          />
        ))}
      </div>

      {/* Item Breakdown List */}
      <div className="space-y-2 text-xs">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className={`p-2.5 rounded-xl border ${item.bgColor} ${item.borderColor} flex items-center justify-between`}
            >
              <div className="flex items-center gap-2">
                <Icon className={`w-3.5 h-3.5 ${item.textColor}`} />
                <div>
                  <span className={`font-semibold ${item.textColor}`}>{item.label}</span>
                  <span className="text-[10px] text-[#5e5f6e] block">{item.desc}</span>
                </div>
              </div>
              <div className="text-right font-mono">
                <span className={`font-bold text-sm ${item.textColor}`}>{item.count}</span>
                <span className="text-[10px] text-[#747686] block">({item.percentage}%)</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
