import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Globe,
  Lock,
  Network,
  Play,
  RefreshCw,
  Settings as SettingsIcon,
  Shield,
  User,
  XCircle,
} from 'lucide-react';
import { apiClient } from '../api/client';

interface NavbarProps {
  onTriggerMonitoring: () => Promise<void>;
  isMonitoring: boolean;
  onOpenAuthModal: () => void;
  currentUser: { username: string } | null;
}

export const Navbar: React.FC<NavbarProps> = ({
  onTriggerMonitoring,
  isMonitoring,
  onOpenAuthModal,
  currentUser,
}) => {
  const [health, setHealth] = useState<{
    status: string;
    tavily_key_configured: boolean;
    llm_key_configured: boolean;
  } | null>(null);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const fetchHealth = async () => {
    try {
      const data = await apiClient.getHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full glass-panel border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand Header */}
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-cyan-600 to-blue-600 shadow-lg shadow-cyan-500/20 text-white">
            <Shield className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-lg tracking-wide text-white">
                Disruption<span className="text-cyan-400">Sentinel</span>
              </span>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/50">
                v1.0 MVP
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">Supply Chain Early-Warning System</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav className="hidden md:flex items-center space-x-1 bg-slate-900/60 p-1 rounded-xl border border-slate-800">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
          >
            <Activity className="w-4 h-4" />
            <span>Dashboard</span>
          </NavLink>

          <NavLink
            to="/network"
            className={({ isActive }) =>
              `flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
          >
            <Network className="w-4 h-4" />
            <span>Supply Network</span>
          </NavLink>

          <NavLink
            to="/alerts"
            className={({ isActive }) =>
              `flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
          >
            <AlertTriangle className="w-4 h-4" />
            <span>Alert Feed</span>
          </NavLink>

          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
              }`
            }
          >
            <SettingsIcon className="w-4 h-4" />
            <span>Settings</span>
          </NavLink>
        </nav>

        {/* Status Indicators & Action Trigger */}
        <div className="flex items-center space-x-3">
          <div className="hidden lg:flex items-center space-x-2 bg-slate-900/40 px-2.5 py-1 rounded-lg border border-slate-800 text-xs">
            <span className="flex items-center space-x-1 text-slate-400">
              <Database className="w-3 h-3" />
              <span>API:</span>
              {health ? (
                <CheckCircle2 className="w-3 h-3 text-emerald-400" />
              ) : (
                <XCircle className="w-3 h-3 text-rose-500" />
              )}
            </span>
            <span className="text-slate-600">|</span>
            <span className="flex items-center space-x-1 text-slate-400">
              <Globe className="w-3 h-3" />
              <span>Tavily:</span>
              {health?.tavily_key_configured ? (
                <span className="text-emerald-400 font-semibold">Active</span>
              ) : (
                <span className="text-amber-400 font-semibold">Simulated</span>
              )}
            </span>
            <span className="text-slate-600">|</span>
            <span className="flex items-center space-x-1 text-slate-400">
              <Activity className="w-3 h-3" />
              <span>LLM:</span>
              {health?.llm_key_configured ? (
                <span className="text-emerald-400 font-semibold">Active</span>
              ) : (
                <span className="text-cyan-400 font-semibold">Heuristic</span>
              )}
            </span>
          </div>

          <button
            onClick={onTriggerMonitoring}
            disabled={isMonitoring}
            className="flex items-center space-x-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-md shadow-cyan-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isMonitoring ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                <span>Scanning...</span>
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Run Cycle</span>
              </>
            )}
          </button>

          <button
            onClick={onOpenAuthModal}
            className="p-1.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-300 hover:text-white hover:border-slate-700 transition-all"
            title={currentUser ? `Logged in as ${currentUser.username}` : 'Login'}
          >
            {currentUser ? (
              <div className="flex items-center space-x-1 px-1 text-xs text-cyan-400">
                <User className="w-3.5 h-3.5" />
                <span className="max-w-[70px] truncate">{currentUser.username}</span>
              </div>
            ) : (
              <Lock className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </header>
  );
};
