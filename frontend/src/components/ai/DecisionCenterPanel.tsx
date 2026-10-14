import React, { useState } from 'react';
import { Send, Sparkles, Terminal, ShieldAlert, CheckCircle, ArrowRight, BrainCircuit } from 'lucide-react';
import { DisruptionEvent } from '../../types/events';

interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  evidence?: {
    risk?: number;
    credibility?: number;
    sources?: number;
    affectedNodes?: string[];
  };
  timestamp: string;
}

const SUGGESTED_PROMPTS = [
  'What disruptions are currently affecting our network?',
  'Which suppliers are exposed?',
  'Why is this event considered moderate credibility?',
  'What downstream facilities could be affected?',
  'Which current event requires review?',
];

export const DecisionCenterPanel: React.FC<{ events?: DisruptionEvent[]; className?: string }> = ({
  events = [],
  className = '',
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      sender: 'assistant',
      text: 'Operational Intelligence Decision Engine initialized. Monitoring active business topology, multi-tier credibility assessments, and deterministic downstream impact paths. How can I assist your supply chain decision-making?',
      evidence: {
        risk: 82,
        credibility: 63.5,
        sources: 2,
        affectedNodes: ['Taiwan Semiconductor Corp', 'Surat Logistics Hub'],
      },
      timestamp: '10:42 AM',
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = (textToSend?: string) => {
    const query = (textToSend || input).trim();
    if (!query) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput('');
    setLoading(true);

    setTimeout(() => {
      let replyText = '';
      let evidence = undefined;

      const lower = query.toLowerCase();
      if (lower.includes('downstream') || lower.includes('facilities') || lower.includes('affect')) {
        replyText =
          'Cross-traversal shows 4 downstream facilities are in the propagation path of the Surat transport disruption. Specifically, Assembly Plant B and Central Distribution Hub depend on Route A with an 80% weight.';
        evidence = {
          risk: 82,
          credibility: 63.5,
          sources: 2,
          affectedNodes: ['Assembly Plant B', 'Central Distribution Hub'],
        };
      } else if (lower.includes('credibility') || lower.includes('why') || lower.includes('moderate')) {
        replyText =
          'Event authenticated at 63.5 / 100 (Moderate Confidence). The publisher is Reuters (Tier 1, 90 pts), with 85% LLM extraction confidence and 75% ML content style score. It is classified as Moderate because only 2 independent sources have corroborated so far.';
        evidence = {
          risk: 74,
          credibility: 63.5,
          sources: 2,
          affectedNodes: ['Reuters Wire'],
        };
      } else if (lower.includes('review') || lower.includes('unconfirmed') || lower.includes('gated')) {
        replyText =
          'There are currently unconfirmed signals gated below the 35.0 threshold. For example, a supplier delay reported on an unverified forum scored 33.5. The system gated it from generating full alerts, pending manual verification.';
        evidence = {
          risk: 45,
          credibility: 33.5,
          sources: 1,
          affectedNodes: ['Unverified Logistics Post'],
        };
      } else {
        replyText =
          'Based on current network telemetry, 3 active disruptions are confirmed. Highest priority is the transport route failure affecting 6 downstream nodes with a combined deterministic risk score of 82/100.';
        evidence = {
          risk: 82,
          credibility: 63.5,
          sources: 2,
          affectedNodes: ['Transport Route A', 'Surat Facility'],
        };
      }

      const aiMsg: Message = {
        id: (Date.now() + 1).toString(),
        sender: 'assistant',
        text: replyText,
        evidence,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, aiMsg]);
      setLoading(false);
    }, 600);
  };

  return (
    <div className={`panel-obsidian rounded-2xl p-6 text-white space-y-5 shadow-2xl ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-lg bg-[#6c47ff]/20 text-[#5de3ff] border border-[#6c47ff]/40">
            <BrainCircuit className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold tracking-tight text-white flex items-center gap-2">
              <span>AI DECISION CENTER</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-[#6c47ff]/30 text-[#5de3ff] border border-[#6c47ff]/50">
                ACTIVE
              </span>
            </h3>
            <p className="text-xs text-[#9394a1]">Synthesizes risk, credibility verification, and graph topology</p>
          </div>
        </div>

        <div className="text-[11px] font-mono text-[#9394a1] hidden sm:block">
          Model: Claude 3.5 / Heuristic Hybrid
        </div>
      </div>

      {/* Suggested Prompts */}
      <div className="space-y-1.5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-[#9394a1] block">
          Operational Inquiries
        </span>
        <div className="flex flex-wrap gap-2">
          {SUGGESTED_PROMPTS.map((prompt) => (
            <button
              key={prompt}
              onClick={() => handleSend(prompt)}
              className="text-xs px-3 py-1.5 rounded-lg bg-[#2f3037] hover:bg-[#393a43] border border-white/10 text-slate-200 transition-colors text-left"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Messages */}
      <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`p-4 rounded-xl border text-xs leading-relaxed space-y-2.5 ${
              m.sender === 'user'
                ? 'bg-[#2f3037] border-white/10 text-white ml-8'
                : 'bg-[#1a1a1f] border-white/5 text-slate-200 mr-2'
            }`}
          >
            <div className="flex items-center justify-between text-[11px] font-mono text-[#9394a1]">
              <span className={m.sender === 'user' ? 'text-[#5de3ff] font-bold' : 'text-[#6c47ff] font-bold'}>
                {m.sender === 'user' ? 'Operator' : 'AI Decision Core'}
              </span>
              <span>{m.timestamp}</span>
            </div>

            <p className="text-slate-100">{m.text}</p>

            {/* Evidence Chips */}
            {m.evidence && (
              <div className="pt-2 border-t border-white/10 flex flex-wrap items-center gap-3 text-[11px] font-mono text-[#9394a1]">
                <span className="text-white font-semibold">Evidence:</span>
                {m.evidence.risk !== undefined && (
                  <span className="text-rose-400">Risk: {m.evidence.risk}</span>
                )}
                {m.evidence.credibility !== undefined && (
                  <span className="text-[#5de3ff]">Credibility: {m.evidence.credibility}</span>
                )}
                {m.evidence.sources !== undefined && (
                  <span className="text-slate-300">Sources: {m.evidence.sources}</span>
                )}
                {m.evidence.affectedNodes && m.evidence.affectedNodes.length > 0 && (
                  <span className="text-amber-300 truncate max-w-xs">
                    Nodes: {m.evidence.affectedNodes.join(', ')}
                  </span>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="p-3 rounded-xl bg-[#1a1a1f] border border-white/5 text-xs text-[#5de3ff] flex items-center gap-2 font-mono">
            <span className="w-2 h-2 rounded-full bg-[#5de3ff] animate-ping" />
            <span>Analyzing graph paths and corroboration evidence...</span>
          </div>
        )}
      </div>

      {/* Input Field */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex items-center gap-2 pt-2 border-t border-white/10"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about disruption exposure, credibility gating, or downstream impact..."
          className="flex-1 bg-[#2f3037] border border-white/10 rounded-lg px-4 py-2.5 text-xs text-white placeholder-[#9394a1] focus:outline-none focus:border-[#6c47ff]"
        />
        <button
          type="submit"
          disabled={!input.trim() || loading}
          className="px-4 py-2.5 rounded-lg bg-[#6c47ff] hover:bg-[#615cf6] text-white text-xs font-semibold flex items-center gap-1.5 transition-colors disabled:opacity-50"
        >
          <Send className="w-3.5 h-3.5" />
          <span>Inquire</span>
        </button>
      </form>
    </div>
  );
};
