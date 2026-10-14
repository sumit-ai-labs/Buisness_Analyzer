import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  AlertOctagon,
  ShieldAlert,
  Layers,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  ArrowRight,
  TrendingUp,
  Globe,
  MapPin,
} from "lucide-react";
import { api } from "../api/client";
import { Alert, DashboardStats } from "../types/risk";
import { BusinessEntity } from "../types/entity";
import { DisruptionEvent, UnconfirmedEventSummary } from "../types/events";
import { KPIStatCard } from "../components/dashboard/KPIStatCard";
import { PipelineStatus } from "../components/dashboard/PipelineStatus";
import { IncidentTable } from "../components/incidents/IncidentTable";
import { IncidentDetailsModal } from "../components/incidents/IncidentDetailsModal";
import { DisruptionTrendChart } from "../components/analytics/DisruptionTrendChart";
import { VerificationBreakdownChart } from "../components/analytics/VerificationBreakdownChart";
import { UnconfirmedSignalsCard } from "../components/verification/UnconfirmedSignalsCard";
import { VerificationBadge, RiskBadge } from "../components/common/Badge";

export const DashboardPage: React.FC = () => {
  const [entities, setEntities] = useState<BusinessEntity[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [events, setEvents] = useState<DisruptionEvent[]>([]);
  const [unconfirmedEvents, setUnconfirmedEvents] = useState<UnconfirmedEventSummary[]>([]);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedEvent, setSelectedEvent] = useState<DisruptionEvent | null>(null);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [ents, alts, evts, unconfirmed, st] = await Promise.all([
        api.getEntities().catch(() => []),
        api.getAlerts().catch(() => []),
        api.getEvents().catch(() => []),
        api.getUnconfirmedEvents().catch(() => []),
        api.getDashboardStats().catch(() => null),
      ]);
      setEntities(ents);
      setAlerts(alts);
      setEvents(evts);
      setUnconfirmedEvents(unconfirmed);
      setStats(st);
    } catch (err) {
      console.error("Failed to load dashboard data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const criticalAlertsCount = alerts.filter(
    (a) => !a.acknowledged
  ).length;

  const activeDisruptionsCount = events.length > 0 ? events.length : alerts.length;
  const unconfirmedCount = stats?.unconfirmed_events ?? unconfirmedEvents.length;
  const ambiguitiesCount = stats?.location_ambiguities ?? 0;

  // Compute breakdown counts for verification chart dynamically from API data
  const highVerified = events.filter((e) => e.credibility?.confidence_label === 'high' || (e.credibility?.authenticity_score ?? 0) >= 80).length;
  const moderateVerified = events.filter((e) => e.credibility?.confidence_label === 'moderate' || ((e.credibility?.authenticity_score ?? 0) >= 60 && (e.credibility?.authenticity_score ?? 0) < 80)).length;
  const lowVerified = events.filter((e) => e.credibility?.confidence_label === 'low' || ((e.credibility?.authenticity_score ?? 0) >= 35 && (e.credibility?.authenticity_score ?? 0) < 60)).length;

  const verificationCounts = {
    high: highVerified,
    moderate: moderateVerified,
    low: lowVerified,
    unconfirmed: unconfirmedCount,
  };

  return (
    <div className="space-y-6">
      {/* 6-Stage Intelligence Pipeline Status */}
      <PipelineStatus />

      {/* SECTION 1: High-Level KPI Strip (5 Cards) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        <KPIStatCard
          label="Active Disruptions"
          value={activeDisruptionsCount}
          context="+3 from latest scan cycle"
          icon={AlertOctagon}
          accent="neutral"
        />

        <KPIStatCard
          label="Critical Risks"
          value={criticalAlertsCount}
          context="Requires immediate operator review"
          icon={ShieldAlert}
          accent="red"
        />

        <KPIStatCard
          label="Unconfirmed (Gated)"
          value={unconfirmedCount}
          context="Held at gate · Credibility < 35"
          icon={ShieldCheck}
          accent="amber"
        />

        <KPIStatCard
          label="Location Ambiguities"
          value={ambiguitiesCount}
          context="Geo-gated · Review required"
          icon={Globe}
          accent="amber"
        />

        <KPIStatCard
          label="Entities at Risk"
          value={entities.length}
          context="Monitored suppliers & routes"
          icon={Layers}
          accent="violet"
        />
      </div>

      {/* SECTION 2: Active Disruptions & Network Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Disruptions Table Preview (2 Cols) */}
        <div className="lg:col-span-2 bg-white border border-[#d9d9de] rounded-2xl p-5 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
            <div>
              <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
                Confirmed Events
              </span>
              <h3 className="font-bold text-[#131316] text-base">
                Active Disruptions ({events.length})
              </h3>
            </div>

            <Link
              to="/disruptions"
              className="text-xs text-[#6c47ff] hover:text-[#615cf6] font-medium flex items-center gap-1"
            >
              <span>View All</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {events.length === 0 ? (
            <div className="py-12 text-center text-xs text-[#747686] space-y-2">
              <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
              <p className="font-semibold text-[#131316]">Zero Confirmed Disruptions Detected</p>
              <p className="max-w-sm mx-auto text-[#5e5f6e]">
                No disruptive events currently affect your supply chain nodes. Run a monitoring scan from the top header to refresh.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {events.slice(0, 4).map((evt) => {
                const assessment = evt.credibility;
                const score = assessment?.authenticity_score ?? 63.5;
                const status = assessment?.confidence_label ?? 'moderate';
                const isGated = assessment?.is_gated ?? false;

                let domain = 'External Source';
                if (evt.source_url) {
                  try {
                    domain = new URL(evt.source_url).hostname.replace('www.', '');
                  } catch {
                    domain = 'News Feed';
                  }
                }

                return (
                  <div
                    key={evt.id}
                    onClick={() => setSelectedEvent(evt)}
                    className="p-3.5 rounded-xl border border-[#d9d9de] hover:border-[#cacacf] hover:bg-[#f7f7f8]/50 transition-all cursor-pointer space-y-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-[#6c47ff]" />
                        <span className="font-semibold text-xs text-[#131316] truncate max-w-sm">
                          {evt.headline}
                        </span>
                      </div>
                      <span className="text-[11px] text-[#747686] whitespace-nowrap">
                        {evt.retrieved_at ? new Date(evt.retrieved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '2m ago'}
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-2">
                        <RiskBadge level={evt.severity_raw === 'high' ? 'high' : 'medium'} />
                        <span className="font-mono text-[11px] font-bold text-[#131316]">
                          Risk {Math.round((score * 0.5) + (evt.confidence * 50))}
                        </span>
                        <VerificationBadge
                          status={status}
                          isGated={isGated}
                          score={score}
                        />
                      </div>

                      <div className="text-[11px] text-[#747686]">
                        Source: <span className="font-mono text-[#131316]">{domain}</span> · View Details →
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Unconfirmed Signals (Gated) & Topology Overview */}
        <div className="space-y-6">
          <UnconfirmedSignalsCard
            unconfirmedEvents={unconfirmedEvents}
          />

          {/* Quick Network Health Card */}
          <div className="p-5 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-3">
            <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
                  Topology Status
                </span>
                <h4 className="text-xs font-bold text-[#131316]">Network Health</h4>
              </div>

              <Link
                to="/network"
                className="text-xs text-[#6c47ff] hover:text-[#615cf6] font-medium"
              >
                Inspect Graph →
              </Link>
            </div>

            <div className="text-xs text-[#5e5f6e] space-y-2">
              <div className="flex justify-between p-2.5 rounded-lg bg-[#f7f7f8] border border-[#eeeef0]">
                <span>Monitored Facilities & Routes:</span>
                <strong className="text-[#131316] font-mono">{entities.length} nodes</strong>
              </div>
              <div className="flex justify-between p-2.5 rounded-lg bg-[#f7f7f8] border border-[#eeeef0]">
                <span>Critical Path Nodes:</span>
                <strong className="text-rose-700 font-mono">
                  {entities.filter((e) => e.criticality === "high").length} nodes
                </strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* SECTION 3: Risk Trend & Verification Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <DisruptionTrendChart />
        <VerificationBreakdownChart counts={verificationCounts} />
      </div>

      {/* Rich Incident Details Modal */}
      {selectedEvent && (
        <IncidentDetailsModal
          event={selectedEvent}
          credibility={selectedEvent.credibility}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  );
};
