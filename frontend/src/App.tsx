import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";
import { ThemeProvider } from "./context/ThemeContext";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { NetworkPage } from "./pages/NetworkPage";
import { AlertsPage } from "./pages/AlertsPage";
import { VerificationPage } from "./pages/VerificationPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AssistantPage } from "./pages/AssistantPage";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { StatusPage } from "./pages/StatusPage";
import { GeoIntelligencePage } from "./pages/GeoIntelligencePage";

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <Router>
        <AppShell>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/disruptions" element={<AlertsPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/verification" element={<VerificationPage />} />
            <Route path="/geo-intelligence" element={<GeoIntelligencePage />} />
            <Route path="/map" element={<GeoIntelligencePage />} />
            <Route path="/network" element={<NetworkPage />} />
            <Route path="/analytics" element={<AnalyticsPage />} />
            <Route path="/assistant" element={<AssistantPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </Router>
    </ThemeProvider>
  );
};

export default App;
