import React from 'react';

export const NetworkLegend: React.FC<{ className?: string }> = ({ className = '' }) => {
  return (
    <div className={`p-3 bg-white/95 backdrop-blur-md border border-[#d9d9de] rounded-xl shadow-sm text-[11px] font-mono space-y-1.5 ${className}`}>
      <span className="text-[10px] uppercase font-bold text-[#747686] block tracking-wider">
        Network Status
      </span>
      <div className="flex items-center gap-3">
        <span className="inline-flex items-center gap-1.5 text-[#5e5f6e]">
          <span className="w-2 h-2 rounded-full bg-emerald-500" /> Normal
        </span>
        <span className="inline-flex items-center gap-1.5 text-[#6c47ff]">
          <span className="w-2 h-2 rounded-full bg-[#6c47ff]" /> Affected
        </span>
        <span className="inline-flex items-center gap-1.5 text-rose-700">
          <span className="w-2 h-2 rounded-full bg-rose-600" /> Critical
        </span>
        <span className="inline-flex items-center gap-1 text-[#747686]">
          <span className="w-3 h-0.5 bg-[#6c47ff]" /> Dependency
        </span>
      </div>
    </div>
  );
};
