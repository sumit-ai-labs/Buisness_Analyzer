import React from 'react';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

interface DisruptionTrendChartProps {
  data?: Array<{ date: string; disruptions: number; critical: number }>;
  className?: string;
}

const DEFAULT_TREND = [
  { date: 'Mon', disruptions: 4, critical: 1 },
  { date: 'Tue', disruptions: 6, critical: 2 },
  { date: 'Wed', disruptions: 8, critical: 2 },
  { date: 'Thu', disruptions: 5, critical: 1 },
  { date: 'Fri', disruptions: 11, critical: 3 },
  { date: 'Sat', disruptions: 7, critical: 1 },
  { date: 'Sun', disruptions: 9, critical: 2 },
];

export const DisruptionTrendChart: React.FC<DisruptionTrendChartProps> = ({
  data = DEFAULT_TREND,
  className = '',
}) => {
  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
            Temporal Analysis
          </span>
          <h4 className="text-xs font-bold text-[#131316]">Disruptions Over Time</h4>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          <span className="flex items-center gap-1.5 text-[#5e5f6e]">
            <span className="w-2 h-2 rounded-full bg-[#6c47ff]" /> Total Detected
          </span>
          <span className="flex items-center gap-1.5 text-rose-700">
            <span className="w-2 h-2 rounded-full bg-rose-500" /> Critical Risk
          </span>
        </div>
      </div>

      <div className="h-60 w-full pt-2">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eeeef0" vertical={false} />
            <XAxis
              dataKey="date"
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
              contentStyle={{
                backgroundColor: '#ffffff',
                border: '1px solid #d9d9de',
                borderRadius: '8px',
                fontSize: '12px',
                boxShadow: '0 2px 8px rgba(19, 19, 22, 0.08)',
              }}
              labelStyle={{ fontWeight: 600, color: '#131316', marginBottom: 4 }}
            />
            <Area
              type="monotone"
              dataKey="disruptions"
              name="Disruptions"
              stroke="#6c47ff"
              strokeWidth={2}
              fill="#6c47ff"
              fillOpacity={0.08}
            />
            <Area
              type="monotone"
              dataKey="critical"
              name="Critical Risks"
              stroke="#e5484d"
              strokeWidth={1.5}
              fill="#e5484d"
              fillOpacity={0.12}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
