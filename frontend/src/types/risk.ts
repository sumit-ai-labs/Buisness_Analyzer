import { BusinessEntity } from "./entity";
import { DisruptionEvent } from "./events";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskAssessment {
  id: string;
  event_id: string;
  entity_id: string;
  severity_score: number;
  factors: Record<string, number>;
  risk_level: RiskLevel;
  computed_at: string;
}

export interface Alert {
  id: string;
  event_id: string;
  risk_assessment_id: string;
  entity_ids: string[];
  message: string;
  dedupe_key: string;
  created_at: string;
  acknowledged: boolean;
  acknowledged_at?: string | null;

  event?: DisruptionEvent;
  risk_assessment?: RiskAssessment;
  affected_entities?: BusinessEntity[];
}

export interface ExplainResponse {
  alert: Alert;
  risk_assessment?: RiskAssessment | null;
  event?: DisruptionEvent;
  impacted_entities?: BusinessEntity[];
  credibility_assessment?: import("./events").CredibilityAssessment | null;
  geo_verification?: import("./geo").GeoVerificationResult | null;
  weather_signal?: {
    status:
      | "checked"
      | "no_coordinates"
      | "not_applicable"
      | "unavailable"
      | "insufficient_coverage"
      | "not_checked"
      | "confirmed"
      | "not_supported";
    classification?:
      | "confirmed"
      | "not_supported"
      | "unavailable"
      | "not_checked"
      | "insufficient_coverage";
    confirms_event: boolean;
    precipitation_mm_24h?: number | null;
    wind_speed_kmh?: number | null;
    explanation?: string | null;
  } | null;
  last_monitored_at?: string | null;
}

export type AlertExplanation = ExplainResponse;

export interface SystemConfig {
  weights: Record<string, number>;
  thresholds: Record<string, number>;
}

export interface DashboardStats {
  total_alerts: number;
  unacknowledged_alerts: number;
  high_critical_alerts: number;
  total_monitored_entities: number;
  unconfirmed_events?: number;
  location_ambiguities?: number;
  last_run_at?: string;
}

export interface MonitoringCycleSummary {
  raw_results_count: number;
  processed_results_count?: number;
  extraction_success_count?: number;
  extraction_failed_count?: number;
  extraction_rejected_count?: number;
  relevant_events_count: number;
  gated_events_count?: number;
  ambiguous_events_count?: number;
  new_assessments_count?: number;
  new_alerts_count: number;
}
