export type DisruptionEventType =
  | 'flood'
  | 'strike'
  | 'closure'
  | 'supplier_failure'
  | 'political'
  | 'weather'
  | 'other';

export type RawSeverity = 'low' | 'medium' | 'high' | 'unclear';

export type ConfidenceLabel = 'high' | 'moderate' | 'low' | 'unconfirmed';

export interface CredibilityAssessment {
  id: string;
  authenticity_score: number; // 0-100
  confidence_label: ConfidenceLabel;
  is_gated: boolean;
  source_domain: string;
  source_tier: string;
  source_reputation_score: number;
  corroborating_source_count: number;
  content_style_score: number;
  llm_extraction_confidence: number;
  factors: Record<string, number>;
  model_version: string;
  assessed_at: string;
}

export interface DisruptionEvent {
  id: string;
  source_url: string;
  source_result_id: string;
  headline: string;
  summary: string;
  event_type: DisruptionEventType;
  location_mentioned: string;
  severity_raw: RawSeverity;
  extracted_entities: string[];
  confidence: number;
  is_relevant: boolean;
  retrieved_at: string;
  analyzed_at: string;
  credibility_assessment_id?: string | null;
  credibility?: CredibilityAssessment | null;
  geo_verification_id?: string | null;
  event_latitude?: number | null;
  event_longitude?: number | null;
  event_city?: string | null;
  location_confidence?: number | null;
  geo_verification?: import('./geo').GeoVerificationResult | null;
}

export interface UnconfirmedEventSummary {
  event_id: string;
  headline: string;
  source_url: string;
  source_domain: string;
  event_type: DisruptionEventType;
  location_mentioned: string;
  authenticity_score: number | null;
  confidence_label: ConfidenceLabel;
  is_gated: true;
  source_tier: string | null;
  corroborating_source_count: number;
  content_style_score: number | null;
  factors: Record<string, number> | null;
  geo_status: string;
  detected_at: string;
}

export interface LocationAmbiguitySummary {
  event_id: string;
  headline: string;
  source_url: string;
  event_type: DisruptionEventType;
  location_mentioned: string;
  authenticity_score: number | null;
  confidence_label: ConfidenceLabel;
  geo_status: string;
  location_confidence: number;
  entity_match_confidence: number;
  ambiguity_reason: string | null;
  candidates: import('./geo').GeoMatchCandidate[];
  detected_at: string;
}

