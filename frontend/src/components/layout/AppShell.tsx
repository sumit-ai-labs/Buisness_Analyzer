import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { TopHeader } from './TopHeader';
import { AuthModal } from '../AuthModal';
import { api } from '../../api/client';

interface AppShellProps {
  children: React.ReactNode;
  onRefreshData?: () => Promise<void> | void;
}

export const AppShell: React.FC<AppShellProps> = ({ children, onRefreshData }) => {
  const [user, setUser] = useState<string | null>(localStorage.getItem('user_name') || 'Admin');
  const [authOpen, setAuthOpen] = useState(false);
  const [isRunningMonitoring, setIsRunningMonitoring] = useState(false);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  const handleRunMonitoring = async () => {
    setIsRunningMonitoring(true);
    setStatusMessage(null);
    try {
      const res = await api.runMonitoringCycle();
      setStatusMessage({
        text: `Cycle complete: ${res.new_alerts_count ?? 0} alerts evaluated across 6 pipeline stages.`,
        type: 'success',
      });
      if (onRefreshData) {
        await onRefreshData();
      }
    } catch (err: any) {
      setStatusMessage({
        text: `Monitoring cycle error: ${err.message || 'Check external API keys in backend'}`,
        type: 'error',
      });
    } finally {
      setIsRunningMonitoring(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('user_name');
    setUser(null);
  };

  return (
    <div className="flex min-h-screen bg-[#f7f7f8] text-[#131316]">
      {/* 240px Fixed Sidebar */}
      <Sidebar
        user={user}
        onOpenAuth={() => setAuthOpen(true)}
        onLogout={handleLogout}
      />

      {/* Main Content Area with Header */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopHeader
          onRunMonitoring={handleRunMonitoring}
          isRunningMonitoring={isRunningMonitoring}
          onOpenAuth={() => setAuthOpen(true)}
          user={user}
        />

        {/* Global Cycle Status Toast / Banner */}
        {statusMessage && (
          <div
            className={`mx-6 mt-4 p-3.5 rounded-xl border text-xs font-medium flex items-center justify-between transition-all ${
              statusMessage.type === 'success'
                ? 'bg-emerald-50 text-emerald-900 border-emerald-200'
                : 'bg-rose-50 text-rose-900 border-rose-200'
            }`}
          >
            <span>{statusMessage.text}</span>
            <button
              onClick={() => setStatusMessage(null)}
              className="text-[#5e5f6e] hover:text-[#131316] font-bold ml-4"
            >
              Dismiss
            </button>
          </div>
        )}

        <main className="flex-1 p-6 max-w-[1400px] w-full mx-auto space-y-6">
          {children}
        </main>

        {/* Professional Minimal Footer */}
        <footer className="border-t border-[#d9d9de] py-4 px-6 text-center text-xs text-[#747686] bg-white">
          <p>
            DisruptionSentinel Enterprise Platform · Real-Time Network Risk & Credibility Intelligence · Built with React Flow & Recharts
          </p>
        </footer>
      </div>

      {/* Operator Authentication Modal */}
      <AuthModal
        isOpen={authOpen}
        onClose={() => setAuthOpen(false)}
        onSuccess={(uname) => {
          localStorage.setItem('user_name', uname);
          setUser(uname);
        }}
      />
    </div>
  );
};
