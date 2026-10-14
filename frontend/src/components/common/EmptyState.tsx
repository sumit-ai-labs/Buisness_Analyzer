import React from 'react';
import { LucideIcon, ShieldCheck } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionText?: string;
  onAction?: () => void;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon = ShieldCheck,
  title,
  description,
  actionText,
  onAction,
  className = '',
}) => {
  return (
    <div className={`p-10 text-center rounded-2xl border border-[#d9d9de] bg-white shadow-sm space-y-3 ${className}`}>
      <div className="w-12 h-12 rounded-full bg-[#f7f7f8] border border-[#d9d9de] flex items-center justify-center mx-auto text-[#5e5f6e]">
        <Icon className="w-6 h-6 text-[#6c47ff]" />
      </div>
      <div className="space-y-1">
        <h4 className="text-sm font-semibold text-[#131316]">{title}</h4>
        <p className="text-xs text-[#5e5f6e] max-w-sm mx-auto leading-relaxed">{description}</p>
      </div>
      {actionText && onAction && (
        <div className="pt-2">
          <button
            onClick={onAction}
            className="px-4 py-2 rounded-md bg-[#6c47ff] hover:bg-[#615cf6] text-white text-xs font-medium transition-colors"
          >
            {actionText}
          </button>
        </div>
      )}
    </div>
  );
};
