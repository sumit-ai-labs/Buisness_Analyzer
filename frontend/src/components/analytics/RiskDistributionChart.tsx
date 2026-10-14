import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, CartesianGrid } from 'recharts';

interface RiskDistributionChartProps {
  distribution?: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  className?: string;
}

export const RiskDistributionChart: React.FC<RiskDistributionChartProps> = ({
  distribution = { critical: 3, high: 7, medium: 12, low: 5 },
  className = '',
}) => {
  const chartData = [
    { name: 'Critical', count: distribution.critical, color: '#e5484d' },
    { name: 'High', count: distribution.high, color: '#f97316' },
    { name: 'Medium', count: distribution.medium, color: '#f59e0b' },
    { name: 'Low', count: distribution.low, color: '#10b981' },
  ];

  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
            Exposure Severity
          </span>
          <h4 className="text-xs font-bold text-[#131316]">Risk Distribution</h4>
        </div>
      </div>

      <div className="h-52 w-full pt-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 10, right: 10, left: -25, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eeeef0" vertical={false} />
            <XAxis
              dataKey="name"
              stroke="#747686"
              fontSize={11}
              tickLine={false}
              axisLine={{ stroke: '#eeeef0' }}
            />
            <YAxis
              stroke="#747686"
              fontSize={11}
              tickLine={false}
              axisLine={false}
              allowDecimals={false}
            />
            <Tooltip
              cursor={{ fill: 'rgba(108, 71, 255, 0.04)' }}
              contentStyle={{
                backgroundColor: '#ffffff',
                border: '1px solid #d9d9de',
                borderRadius: '8px',
                fontSize: '12px',
              }}
            />
            <Bar dataKey="count" radius={[4, 4, 0, 0]}>
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-4 gap-2 pt-2 border-t border-[#eeeef0] text-center text-[11px] font-mono">
        <div>
          <span className="text-[#747686] block text-[10px]">CRITICAL</span>
          <span className="font-bold text-rose-700">{distribution.critical}</span>
        </div>
        <div>
          <span className="text-[#747686] block text-[10px]">HIGH</span>
          <span className="font-bold text-orange-600">{distribution.high}</span>
        </div>
        <div>
          <span className="text-[#747686] block text-[10px]">MEDIUM</span>
          <span className="font-bold text-amber-600">{distribution.medium}</span>
        </div>
        <div>
          <span className="text-[#747686] block text-[10px]">LOW</span>
          <span className="font-bold text-emerald-600">{distribution.low}</span>
        </div>
      </div>
    </div>
  );
};
