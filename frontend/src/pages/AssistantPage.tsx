import React, { useState, useEffect } from 'react';
import { DecisionCenterPanel } from '../components/ai/DecisionCenterPanel';
import { api } from '../api/client';
import { DisruptionEvent } from '../types/events';
import { Bot, Sparkles, BrainCircuit, ShieldAlert, Layers } from 'lucide-react';

export const AssistantPage: React.FC = () => {
  const [events, setEvents] = useState<DisruptionEvent[]>([]);

  useEffect(() => {
    api.getEvents().then(setEvents).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-1">
        <div className="text-[11px] font-mono uppercase text-[#747686]">
          AI Operational Decision Center
        </div>
        <h1 className="text-xl font-bold tracking-tight text-[#131316] flex items-center gap-2">
          <Bot className="w-5 h-5 text-[#6c47ff]" />
          <span>Operational Risk & Verification Intelligence</span>
        </h1>
        <p className="text-xs text-[#5e5f6e]">
          Query real-time network vulnerabilities, explain why events passed or were gated by verification, and predict downstream supply chain bottlenecks.
        </p>
      </div>

      {/* Decision Center Obsidian Panel */}
      <DecisionCenterPanel events={events} />

      {/* Capabilities Overview Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
        <div className="p-4 bg-white border border-[#d9d9de] rounded-xl space-y-1 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-[#131316]">
            <BrainCircuit className="w-4 h-4 text-[#6c47ff]" />
            <span>Downstream Path Tracing</span>
          </div>
          <p className="text-[11px] text-[#747686]">
            Explores topological dependencies across suppliers, warehouses, routes, and assembly factories.
          </p>
        </div>

        <div className="p-4 bg-white border border-[#d9d9de] rounded-xl space-y-1 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-[#131316]">
            <ShieldAlert className="w-4 h-4 text-amber-600" />
            <span>Credibility Audit & Gating</span>
          </div>
          <p className="text-[11px] text-[#747686]">
            Interrogates domain reputation tiers, cross-source corroboration, and linguistic clickbait scores.
          </p>
        </div>

        <div className="p-4 bg-white border border-[#d9d9de] rounded-xl space-y-1 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-[#131316]">
            <Layers className="w-4 h-4 text-[#5e5f6e]" />
            <span>Deterministic Scoring</span>
          </div>
          <p className="text-[11px] text-[#747686]">
            Audits the 5-factor mathematical risk calculation: dependency, criticality, lead-time, single-source, and extraction confidence.
          </p>
        </div>
      </div>
    </div>
  );
};
