import { BusinessEntity, BusinessRelationship, NetworkGraphData } from "../types/entity";
import { Alert, AlertExplanation, DashboardStats, MonitoringCycleSummary, SystemConfig } from "../types/risk";
import { DisruptionEvent, LocationAmbiguitySummary, UnconfirmedEventSummary } from "../types/events";

const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  public status: number;
  public data: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem("jwt_token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorMsg = `HTTP error! status: ${response.status}`;
    let errorData = null;
    try {
      errorData = await response.json();
      if (errorData?.detail) {
        errorMsg = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
      }
    } catch (_) {
      // Ignore JSON parse errors
    }
    throw new ApiError(response.status, errorMsg, errorData);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  // Auth
  getToken: () => localStorage.getItem("jwt_token"),
  getMe: () => request<{ username: string }>("/auth/me"),
  login: async (username: string, password: string): Promise<{ access_token: string }> => {
    const formData = new URLSearchParams();
    formData.append("username", username);
    formData.append("password", password);
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: formData,
    });
    if (!response.ok) throw new Error("Invalid credentials");
    const data = await response.json();
    localStorage.setItem("jwt_token", data.access_token);
    return data;
  },

  // Health
  checkHealth: () => request<{ status: string; env: string; tavily_key_configured: boolean; llm_key_configured: boolean; llm_provider: string }>("/health"),
  getHealth: () => request<{ status: string; env: string; tavily_key_configured: boolean; llm_key_configured: boolean; llm_provider: string }>("/health"),

  // Entities
  getEntities: () => request<BusinessEntity[]>("/entities"),
  listEntities: () => request<BusinessEntity[]>("/entities"),
  getEntity: (id: string) => request<BusinessEntity>(`/entities/${id}`),
  createEntity: (data: Partial<BusinessEntity>) => request<BusinessEntity>("/entities", { method: "POST", body: JSON.stringify(data) }),
  updateEntity: (id: string, patch: Partial<BusinessEntity>) => request<BusinessEntity>(`/entities/${id}`, { method: "PUT", body: JSON.stringify(patch) }),
  deleteEntity: (id: string) => request<void>(`/entities/${id}`, { method: "DELETE" }),
  getDownstream: (id: string, maxDepth = 3) => request<BusinessEntity[]>(`/entities/${id}/downstream?max_depth=${maxDepth}`),
  getDownstreamEntities: (id: string, maxDepth = 3) => request<BusinessEntity[]>(`/entities/${id}/downstream?max_depth=${maxDepth}`),

  // Relationships
  getRelationships: () => request<BusinessRelationship[]>("/relationships"),
  listRelationships: () => request<BusinessRelationship[]>("/relationships"),
  createRelationship: (data: Partial<BusinessRelationship>) => request<BusinessRelationship>("/relationships", { method: "POST", body: JSON.stringify(data) }),
  deleteRelationship: (id: string) => request<void>(`/relationships/${id}`, { method: "DELETE" }),

  // Network Graph JSON for React Flow
  getNetworkGraph: () => request<NetworkGraphData>("/network"),

  // Monitoring Execution
  runMonitoringCycle: () =>
    request<MonitoringCycleSummary>("/monitor/run", { method: "POST" }),

  // Events & Alerts
  getEvents: () => request<DisruptionEvent[]>("/events"),
  getUnconfirmedEvents: () => request<UnconfirmedEventSummary[]>("/events/unconfirmed"),
  getEventCredibility: (id: string) => request<import("../types/events").CredibilityAssessment>(`/events/${id}/credibility`),
  getDashboardStats: () => request<DashboardStats>("/dashboard/stats"),
  getAlerts: (params?: { risk_level?: string; acknowledged?: boolean }) => {
    const query = new URLSearchParams();
    if (params?.risk_level) query.append("risk_level", params.risk_level);
    if (params?.acknowledged !== undefined) query.append("acknowledged", String(params.acknowledged));
    return request<Alert[]>(`/alerts?${query.toString()}`);
  },
  listAlerts: (risk_level?: string) => {
    const query = new URLSearchParams();
    if (risk_level) query.append("risk_level", risk_level);
    return request<Alert[]>(`/alerts?${query.toString()}`);
  },
  acknowledgeAlert: (id: string) => request<Alert>(`/alerts/${id}/acknowledge`, { method: "POST" }),
  explainAlert: (id: string) => request<AlertExplanation>(`/alerts/${id}/explain`),

  // Config
  getConfig: () => request<SystemConfig>("/config"),
  getSystemConfig: () => request<SystemConfig>("/config"),
  updateConfig: (data: Partial<SystemConfig>) => request<any>("/config", { method: "PUT", body: JSON.stringify(data) }),
  updateSystemConfig: (data: Partial<SystemConfig>) => request<any>("/config", { method: "PUT", body: JSON.stringify(data) }),

  // Geographic Intelligence
  getMapData: () => request<import("../types/geo").MapDataResponse>("/geo/map-data"),
  getEventGeoVerification: (eventId: string) => request<import("../types/geo").GeoVerificationResult>(`/geo/events/${eventId}`),
  getEventGeoMatches: (eventId: string) => request<any>(`/geo/events/${eventId}/matches`),
  getLocationAmbiguities: () => request<LocationAmbiguitySummary[]>("/geo/ambiguities"),
  resolveLocation: (query: string) => request<import("../types/geo").EventLocation>("/geo/resolve", { method: "POST", body: JSON.stringify({ query }) }),
  getEntityLocation: (entityId: string) => request<any>(`/entities/${entityId}/location`),
  getGeoConfig: () => request<import("../types/geo").GeoConfig>("/geo/config"),
  updateGeoConfig: (data: Partial<import("../types/geo").GeoConfig>) => request<import("../types/geo").GeoConfig>("/geo/config", { method: "PUT", body: JSON.stringify(data) }),
  geocodeEntities: () => request<import("../types/geo").GeocodeEntitiesResult>("/geo/geocode-entities", { method: "POST" }),
  seedDemoGeoData: () => request<{ message: string; entities_count: number; events_count: number }>("/geo/seed-demo", { method: "POST" }),
};

export const apiClient = api;
