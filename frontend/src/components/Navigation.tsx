import React from "react";
import { NavLink } from "react-router-dom";
import { ShieldAlert, Layers, LayoutDashboard, Bell, Settings, Radio } from "lucide-react";

export const Navigation: React.FC = () => {
  return (
    <header className="bg-panel border-b border-panelBorder sticky top-0 z-40 backdrop-blur-md bg-panel/90">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand Logo & Name */}
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-blue-600/20 text-blue-400 border border-blue-500/30">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <div className="font-bold text-white tracking-tight flex items-center gap-2">
                <span>Disruption Sentinel</span>
                <span className="text-[10px] font-mono bg-blue-950 text-blue-300 border border-blue-800/60 px-1.5 py-0.5 rounded">
                  EARLY-WARNING
                </span>
              </div>
              <div className="text-[11px] text-slate-400">Continuous Business Network Monitoring</div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="flex items-center space-x-1">
            <NavLink
              to="/"
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors ${
                  isActive
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                    : "text-slate-300 hover:text-white hover:bg-panelHover"
                }`
              }
            >
              <LayoutDashboard className="w-4 h-4" /> Dashboard
            </NavLink>

            <NavLink
              to="/network"
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors ${
                  isActive
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                    : "text-slate-300 hover:text-white hover:bg-panelHover"
                }`
              }
            >
              <Layers className="w-4 h-4" /> Network Setup
            </NavLink>

            <NavLink
              to="/alerts"
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors ${
                  isActive
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                    : "text-slate-300 hover:text-white hover:bg-panelHover"
                }`
              }
            >
              <Bell className="w-4 h-4" /> Alerts Feed
            </NavLink>

            <NavLink
              to="/settings"
              className={({ isActive }) =>
                `px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors ${
                  isActive
                    ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                    : "text-slate-300 hover:text-white hover:bg-panelHover"
                }`
              }
            >
              <Settings className="w-4 h-4" /> Settings
            </NavLink>
          </nav>

          {/* Monitoring Status Badge */}
          <div className="flex items-center gap-2 text-xs text-slate-400 bg-background/60 border border-panelBorder px-3 py-1.5 rounded-full">
            <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
            <span>Pipeline Active</span>
          </div>
        </div>
      </div>
    </header>
  );
};
