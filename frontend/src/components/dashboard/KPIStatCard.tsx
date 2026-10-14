import React from 'react';
import { LucideIcon } from 'lucide-react';

interface KPIStatCardProps {
  label: string;
  value: number | string;
  context: string;
  icon?: LucideIcon;
  badge?: string;
  accent?: 'violet' | 'red' | 'amber' | 'neutral';
  className?: string;
}

export const KPIStatCard: React.FC<KPIStatCardProps> = ({
  label,
  value,
  context,
  icon: Icon,
  badge,
  accent = 'neutral',
  className = '',
}) => {
  const getAccentNumberClass = () => {
    switch (accent) {
      case 'red':
        return 'text-[#d32f2f]';
      case 'violet':
        return 'text-[#6c47ff]';
      case 'amber':
        return 'text-[#d97706]';
      default:
        return 'text-[#131316]';
    }
  };

  return (
    <div className={`p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm hover:border-[#cacacf] transition-all space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono uppercase tracking-wider text-[#747686] font-semibold">
          {label}
        </span>
        {Icon && (
          <div className="p-1.5 rounded-lg bg-[#f7f7f8] text-[#5e5f6e] border border-[#eeeef0]">
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>

      <div className="flex items-baseline gap-2">
        <span className={`text-3xl font-bold font-mono tracking-tight ${getAccentNumberClass()}`}>
          {value}
        </span>
        {badge && (
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#f7f7f8] border border-[#d9d9de] text-[#5e5f6e]">
            {badge}
          </span>
        )}
      </div>

      <div className="text-xs text-[#747686] font-normal pt-1 border-t border-[#eeeef0]">
        {context}
      </div>
    </div>
  );
};
