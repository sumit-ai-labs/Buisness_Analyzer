import React from 'react';
import { Play, RefreshCw, Bell, User, Loader2, Moon, Sun } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { useTheme } from '../../context/ThemeContext';

interface TopHeaderProps {
  onRunMonitoring: () => void;
  isRunningMonitoring?: boolean;
  lastUpdated?: string;
  onOpenAuth?: () => void;
  user?: string | null;
  className?: string;
}

export const TopHeader: React.FC<TopHeaderProps> = ({
  onRunMonitoring,
  isRunningMonitoring = false,
  lastUpdated = '2 min ago',
  onOpenAuth,
  user,
  className = '',
}) => {
  const location = useLocation();
  const { theme, toggleTheme } = useTheme();

  const getPageInfo = () => {
    switch (location.pathname) {
      case '/':
        return { title: 'Business Overview', breadcrumb: 'Intelligence / Overview' };
      case '/disruptions':
      case '/alerts':
        return { title: 'Disruption Incidents & Alerts', breadcrumb: 'Intelligence / Disruptions' };
      case '/verification':
        return { title: 'Credibility Verification Hub', breadcrumb: 'Intelligence / Verification' };
      case '/network':
        return { title: 'Business Network Topology', breadcrumb: 'Intelligence / Network' };
      case '/analytics':
        return { title: 'Risk & Verification Analytics', breadcrumb: 'Intelligence / Analytics' };
      case '/assistant':
        return { title: 'AI Operational Decision Center', breadcrumb: 'Intelligence / AI Assistant' };
      case '/reports':
        return { title: 'Executive Audit & Reporting', breadcrumb: 'Intelligence / Reports' };
      case '/settings':
        return { title: 'System Configuration', breadcrumb: 'System / Risk Tuning' };
      case '/status':
        return { title: 'System & API Readiness', breadcrumb: 'System / Status' };
      default:
        return { title: 'Disruption Platform', breadcrumb: 'Intelligence / Overview' };
    }
  };

  const { title, breadcrumb } = getPageInfo();

  return (
    <header className={`h-16 bg-white border-b border-[#d9d9de] px-6 flex items-center justify-between sticky top-0 z-20 ${className}`}>
      {/* Left Context & Title */}
      <div className="space-y-0.5">
        <div className="text-[11px] font-mono text-[#747686]">
          {breadcrumb}
        </div>
        <h1 className="text-base font-bold text-[#131316] tracking-tight">
          {title}
        </h1>
      </div>

      {/* Right Controls & Telemetry */}
      <div className="flex items-center gap-3">
        {/* Monitoring Active Status Dot */}
        <div className="hidden sm:flex items-center gap-2 text-xs font-mono text-[#5e5f6e] bg-[#f7f7f8] border border-[#d9d9de] px-3 py-1.5 rounded-full">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Monitoring Active</span>
          <span className="text-[#9394a1] text-[10px]">· Scan {lastUpdated}</span>
        </div>

        {/* Trigger Run Monitoring Button */}
        <button
          onClick={onRunMonitoring}
          disabled={isRunningMonitoring}
          className="btn-primary"
          title="Run 6-stage disruption intelligence cycle"
        >
          {isRunningMonitoring ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Scanning...</span>
            </>
          ) : (
            <>
              <Play className="w-3.5 h-3.5" />
              <span>Run Monitoring</span>
            </>
          )}
        </button>

        {/* Dark / Light Mode Switcher */}
        <button
          onClick={toggleTheme}
          className="p-2 rounded-lg text-[#5e5f6e] hover:text-[#131316] hover:bg-[#eeeef0] transition-colors border border-transparent hover:border-[#d9d9de]"
          title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          aria-label="Toggle theme"
        >
          {theme === 'dark' ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-[#6c47ff]" />
          )}
        </button>

        {/* Notifications Icon */}
        <button
          className="p-2 rounded-lg text-[#5e5f6e] hover:text-[#131316] hover:bg-[#eeeef0] transition-colors relative"
          title="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="w-1.5 h-1.5 rounded-full bg-[#6c47ff] absolute top-2 right-2" />
        </button>

        {/* User / Profile Menu */}
        <button
          onClick={onOpenAuth}
          className="p-1.5 rounded-lg border border-[#d9d9de] hover:bg-[#eeeef0] text-[#131316] transition-colors flex items-center gap-1.5 text-xs font-medium"
        >
          <User className="w-4 h-4 text-[#6c47ff]" />
          <span className="hidden md:inline">{user || 'Operator'}</span>
        </button>
      </div>
    </header>
  );
};
