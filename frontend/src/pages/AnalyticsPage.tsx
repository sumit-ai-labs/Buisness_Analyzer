import React, { useState, useEffect } from 'react';
import { BarChart3, Filter, Calendar, TrendingUp, ShieldAlert, CheckCircle, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { DisruptionTrendChart } from '../components/analytics/DisruptionTrendChart';
import { RiskDistributionChart } from '../components/analytics/RiskDistributionChart';
import { VerificationBreakdownChart } from '../components/analytics/VerificationBreakdownChart';
import { Alert } from '../types/risk';
import { DisruptionEvent, UnconfirmedEventSummary } from '../types/events';

export const AnalyticsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [events, setEvents] = useState<DisruptionEvent[]>([]);
  const [unconfirmedEvents, setUnconfirmedEvents] = useState<UnconfirmedEventSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('7d');

  const loadData = async () => {
    setLoading(true);
    try {
      const [alts, evts, unconfirmed] = await Promise.all([
        api.getAlerts().catch(() => []),
        api.getEvents().catch(() => []),
        api.getUnconfirmedEvents().catch(() => []),
      ]);
      setAlerts(alts);
      setEvents(evts);
      setUnconfirmedEvents(unconfirmed);
    } catch (err) {
      console.error('Failed to load analytics data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const criticalCount = 0;
  const highCount = alerts.filter((a) => !a.acknowledged).length;
  const mediumCount = 0;
  const lowCount = alerts.filter((a) => a.acknowledged).length;

  const highVerified = events.filter((e) => e.credibility?.confidence_label === 'high' || (e.credibility?.authenticity_score ?? 0) >= 80).length;
  const moderateVerified = events.filter((e) => e.credibility?.confidence_label === 'moderate' || ((e.credibility?.authenticity_score ?? 0) >= 60 && (e.credibility?.authenticity_score ?? 0) < 80)).length;
  const lowVerified = events.filter((e) => e.credibility?.confidence_label === 'low' || ((e.credibility?.authenticity_score ?? 0) >= 35 && (e.credibility?.authenticity_score ?? 0) < 60)).length;

  const verificationCounts = {
    high: highVerified,
    moderate: moderateVerified,
    low: lowVerified,
    unconfirmed: unconfirmedEvents.length,
  };

  return (
    <div className="space-y-6">
      {/* Header with Filters */}
      <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="text-[11px] font-mono uppercase text-[#747686]">
            Historical Intelligence & Metrics
          </div>
          <h1 className="text-xl font-bold tracking-tight text-[#131316] flex items-center gap-2 mt-0.5">
            <BarChart3 className="w-5 h-5 text-[#6c47ff]" />
            <span>Risk & Verification Analytics</span>
          </h1>
          <p className="text-xs text-[#5e5f6e] mt-1">
            Analyze disruption temporal volumes, exposure risk distributions, and credibility verification rates.
          </p>
        </div>

        {/* Date Range Selector */}
        <div className="flex items-center gap-2">
          <div className="flex items-center p-1 rounded-lg bg-[#f7f7f8] border border-[#d9d9de] text-xs font-medium">
            <button
              onClick={() => setTimeRange('24h')}
              className={`px-3 py-1.5 rounded-md transition-all ${
                timeRange === '24h'
                  ? 'bg-[#6c47ff] text-white shadow-sm'
                  : 'text-[#5e5f6e] hover:text-[#131316]'
              }`}
            >
              24h
            </button>
            <button
              onClick={() => setTimeRange('7d')}
              className={`px-3 py-1.5 rounded-md transition-all ${
                timeRange === '7d'
                  ? 'bg-[#6c47ff] text-white shadow-sm'
                  : 'text-[#5e5f6e] hover:text-[#131316]'
              }`}
            >
              7 Days
            </button>
            <button
              onClick={() => setTimeRange('30d')}
              className={`px-3 py-1.5 rounded-md transition-all ${
                timeRange === '30d'
                  ? 'bg-[#6c47ff] text-white shadow-sm'
                  : 'text-[#5e5f6e] hover:text-[#131316]'
              }`}
            >
              30 Days
            </button>
          </div>

          <button
            onClick={loadData}
            disabled={loading}
            className="btn-secondary"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Primary Analytics Chart */}
      <DisruptionTrendChart />

      {/* Secondary Analytics Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <RiskDistributionChart
          distribution={{
            critical: criticalCount,
            high: highCount,
            medium: mediumCount,
            low: lowCount,
          }}
        />

        <VerificationBreakdownChart counts={verificationCounts} />
      </div>
    </div>
  );
};
