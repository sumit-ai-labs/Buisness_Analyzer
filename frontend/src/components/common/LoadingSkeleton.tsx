import React from 'react';

interface LoadingSkeletonProps {
  stage?: string;
  count?: number;
  className?: string;
}

export const LoadingSkeleton: React.FC<LoadingSkeletonProps> = ({
  stage,
  count = 3,
  className = '',
}) => {
  return (
    <div className={`space-y-4 p-6 bg-white border border-[#d9d9de] rounded-2xl ${className}`}>
      {stage && (
        <div className="flex items-center gap-2 text-xs font-mono text-[#6c47ff]">
          <span className="w-2 h-2 rounded-full bg-[#6c47ff] animate-ping" />
          <span>{stage}</span>
        </div>
      )}
      <div className="space-y-3 animate-pulse">
        {Array.from({ length: count }).map((_, i) => (
          <div key={i} className="space-y-2">
            <div className="h-4 bg-[#eeeef0] rounded-md w-3/4" />
            <div className="h-3 bg-[#f7f7f8] rounded-md w-1/2" />
          </div>
        ))}
      </div>
    </div>
  );
};
