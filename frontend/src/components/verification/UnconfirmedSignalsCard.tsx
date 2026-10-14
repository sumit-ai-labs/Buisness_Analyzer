import React from 'react';
import { UnconfirmedEventSummary } from '../../types/events';
import { AlertCircle, ArrowRight, ShieldAlert } from 'lucide-react';
import { Link } from 'react-router-dom';

interface UnconfirmedSignalsCardProps {
  unconfirmedEvents: UnconfirmedEventSummary[];
  onSelectEvent?: (event: UnconfirmedEventSummary) => void;
  className?: string;
}

export const UnconfirmedSignalsCard: React.FC<UnconfirmedSignalsCardProps> = ({
  unconfirmedEvents,
  onSelectEvent,
  className = '',
}) => {
  return (
    <div className={`p-5 bg-white border border-[#d9d9de] rounded-2xl space-y-4 shadow-sm ${className}`}>
      <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-amber-600" />
          <h4 className="text-xs font-bold uppercase tracking-wider text-[#131316]">
            Unconfirmed Signals (Gated)
          </h4>
        </div>
        <span className="px-2 py-0.5 rounded-full text-xs font-mono font-bold bg-amber-50 text-amber-800 border border-amber-200">
          {unconfirmedEvents.length}
        </span>
      </div>

      <p className="text-xs text-[#5e5f6e] leading-relaxed">
        Signals detected below the credibility gate (&lt; 35 score). Retained for manual operator review without triggering downstream alerts.
      </p>

      {unconfirmedEvents.length === 0 ? (
        <div className="py-6 text-center text-xs text-[#747686] bg-[#f7f7f8] rounded-xl border border-[#eeeef0] space-y-1">
          <p className="font-medium text-[#5e5f6e]">No unconfirmed signals</p>
          <p className="text-[11px]">All detected intelligence currently meets confidence thresholds.</p>
        </div>
      ) : (
        <div className="space-y-2.5">
          {unconfirmedEvents.slice(0, 4).map((evt) => {
            const score = evt.authenticity_score ?? 32.5;
            let domain = 'Unknown source';
            if (evt.source_url) {
              try {
                domain = new URL(evt.source_url).hostname.replace('www.', '');
              } catch {
                domain = evt.source_domain || 'Unknown source';
              }
            }

            return (
              <div
                key={evt.event_id}
                onClick={() => onSelectEvent && onSelectEvent(evt)}
                className={`p-3 rounded-xl bg-amber-50/40 border border-amber-200/80 hover:border-amber-300 hover:bg-amber-50/70 transition-all text-xs space-y-1.5 ${
                  onSelectEvent ? 'cursor-pointer' : ''
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-1.5 font-semibold text-[#131316]">
                    <AlertCircle className="w-3.5 h-3.5 text-amber-600 shrink-0 mt-0.5" />
                    <span className="truncate max-w-[240px]">{evt.headline || 'Disruption report detected'}</span>
                  </div>
                  <span className="font-mono text-[11px] font-bold text-amber-800 bg-amber-100/80 px-1.5 py-0.5 rounded shrink-0">
                    Credibility {score.toFixed(1)}
                  </span>
                </div>

                <div className="text-[11px] text-[#5e5f6e] flex items-center justify-between">
                  <span className="truncate max-w-[200px]">
                    {domain} · {evt.location_mentioned || evt.event_type}
                  </span>
                  <span className="text-[10px] text-amber-700 font-medium">Needs review</span>
                </div>
              </div>
            );
          })}

          <div className="pt-2 text-right">
            <Link
              to="/verification"
              className="text-xs text-[#6c47ff] hover:text-[#615cf6] font-medium inline-flex items-center gap-1"
            >
              <span>Review all signals in Verification Hub</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
};
