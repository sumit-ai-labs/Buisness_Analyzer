import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  AlertOctagon,
  ShieldCheck,
  Network,
  GitGraph,
  BarChart3,
  Bot,
  FileText,
  Settings,
  Activity,
  Layers,
  Globe,
  Sliders,
  User,
  LogOut,
} from 'lucide-react';

interface SidebarProps {
  user?: string | null;
  onOpenAuth?: () => void;
  onLogout?: () => void;
  className?: string;
}

export const Sidebar: React.FC<SidebarProps> = ({
  user,
  onOpenAuth,
  onLogout,
  className = '',
}) => {
  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
      isActive
        ? 'bg-[#6c47ff] text-white shadow-sm'
        : 'text-[#5e5f6e] hover:text-[#131316] hover:bg-[#eeeef0]'
    }`;

  return (
    <aside className={`w-60 bg-white border-r border-[#d9d9de] flex flex-col justify-between h-screen sticky top-0 shrink-0 z-30 select-none ${className}`}>
      <div className="p-4 space-y-6 overflow-y-auto">
        {/* Brand Header */}
        <div className="flex items-center gap-2.5 px-2">
          <div className="w-8 h-8 rounded-lg bg-[#6c47ff] text-white flex items-center justify-center font-bold text-base shadow-sm">
            S
          </div>
          <div>
            <div className="font-bold text-xs text-[#131316] tracking-tight leading-tight">
              SENTINEL INTEL
            </div>
            <div className="text-[10px] text-[#747686] font-mono">
              Business Disruption Engine
            </div>
          </div>
        </div>

        {/* SECTION 1: Operational Monitoring */}
        <div className="space-y-1">
          <span className="px-3 text-[10px] font-mono uppercase tracking-wider text-[#747686] font-semibold block mb-2">
            Intelligence
          </span>

          <NavLink to="/" className={navItemClass}>
            <LayoutDashboard className="w-4 h-4 shrink-0" />
            <span>Overview</span>
          </NavLink>

          <NavLink to="/disruptions" className={navItemClass}>
            <AlertOctagon className="w-4 h-4 shrink-0" />
            <span>Disruptions</span>
          </NavLink>

          <NavLink to="/verification" className={navItemClass}>
            <ShieldCheck className="w-4 h-4 shrink-0" />
            <span className="flex-1">Verification</span>
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-amber-100 text-amber-900 border border-amber-200">
              GATE
            </span>
          </NavLink>

          <NavLink to="/geo-intelligence" className={navItemClass}>
            <Globe className="w-4 h-4 shrink-0" />
            <span className="flex-1">Geo-Spatial Intel</span>
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.2 rounded bg-violet-100 text-violet-900 border border-violet-200">
              GPS
            </span>
          </NavLink>

          <NavLink to="/network" className={navItemClass}>
            <Network className="w-4 h-4 shrink-0" />
            <span>Business Network</span>
          </NavLink>

          <NavLink to="/analytics" className={navItemClass}>
            <BarChart3 className="w-4 h-4 shrink-0" />
            <span>Analytics</span>
          </NavLink>

          <NavLink to="/assistant" className={navItemClass}>
            <Bot className="w-4 h-4 shrink-0" />
            <span>AI Decision Center</span>
          </NavLink>

          <NavLink to="/reports" className={navItemClass}>
            <FileText className="w-4 h-4 shrink-0" />
            <span>Reports & Audit</span>
          </NavLink>
        </div>

        {/* SECTION 2: Configuration */}
        <div className="space-y-1 pt-2 border-t border-[#eeeef0]">
          <span className="px-3 text-[10px] font-mono uppercase tracking-wider text-[#747686] font-semibold block mb-2">
            Configuration
          </span>

          <NavLink to="/network?tab=entities" className={navItemClass}>
            <Layers className="w-4 h-4 shrink-0" />
            <span>Business Entities</span>
          </NavLink>

          <NavLink to="/settings" className={navItemClass}>
            <Sliders className="w-4 h-4 shrink-0" />
            <span>Risk Scoring Tuning</span>
          </NavLink>
        </div>

        {/* SECTION 3: System */}
        <div className="space-y-1 pt-2 border-t border-[#eeeef0]">
          <span className="px-3 text-[10px] font-mono uppercase tracking-wider text-[#747686] font-semibold block mb-2">
            System
          </span>

          <NavLink to="/status" className={navItemClass}>
            <Activity className="w-4 h-4 shrink-0" />
            <span>System Health & API</span>
          </NavLink>
        </div>
      </div>

      {/* Operator User Footer */}
      <div className="p-4 border-t border-[#d9d9de] bg-[#f7f7f8]/80">
        {user ? (
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2 truncate">
              <div className="w-7 h-7 rounded-full bg-[#131316] text-white flex items-center justify-center font-bold text-xs uppercase">
                {user.charAt(0)}
              </div>
              <div className="truncate">
                <span className="font-semibold text-[#131316] block truncate">{user}</span>
                <span className="text-[10px] text-[#747686] block">Operator · Admin</span>
              </div>
            </div>
            {onLogout && (
              <button
                onClick={onLogout}
                className="p-1 text-[#747686] hover:text-[#131316] transition-colors"
                title="Sign Out"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        ) : (
          <button
            onClick={onOpenAuth}
            className="w-full py-2 px-3 rounded-lg bg-white hover:bg-[#eeeef0] border border-[#d9d9de] text-[#131316] text-xs font-semibold flex items-center justify-center gap-2 transition-colors shadow-sm"
          >
            <User className="w-3.5 h-3.5 text-[#6c47ff]" />
            <span>Operator Sign In</span>
          </button>
        )}
      </div>
    </aside>
  );
};
