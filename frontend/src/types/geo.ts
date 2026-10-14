export type GeoStatus =
  | 'LOCATION_VERIFIED'
  | 'LOCATION_PARTIALLY_VERIFIED'
  | 'LOCATION_AMBIGUOUS'
  | 'LOCATION_UNRESOLVED';

export type CandidateMatchStatus = 'MATCH' | 'AMBIGUOUS' | 'REJECTED' | 'UNRESOLVED';

export interface EventLocation {
  raw_text: string;
  name?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  country?: string | null;
  postal_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  confidence: number;
  source: string;
  is_resolved: boolean;
}

export interface GeoMatchCandidate {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  entity_location: string;
  entity_latitude?: number | null;
  entity_longitude?: number | null;
  distance_km?: number | null;
  city_match: boolean;
  state_match: boolean;
  country_match: boolean;
  name_similarity: number;
  geo_confidence: number;
  status: CandidateMatchStatus;
  match_reasons: string[];
}

export interface GeoVerificationResult {
  id: string;
  event_id: string;
  event_location: EventLocation;
  status: GeoStatus;
  location_confidence: number; // 0 - 100
  entity_match_confidence: number; // 0 - 100
  primary_matched_entity_id?: string | null;
  primary_matched_entity_name?: string | null;
  distance_km?: number | null;
  candidates: GeoMatchCandidate[];
  ambiguity_reason?: string | null;
  verified_at: string;
}

export interface MapEntityItem {
  id: string;
  name: string;
  type: string;
  location: string;
  city?: string | null;
  country?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  criticality: 'low' | 'medium' | 'high';
  status: 'active' | 'inactive';
}

export interface MapEventItem {
  id: string;
  headline: string;
  event_type: string;
  severity: string;
  location_mentioned: string;
  latitude?: number | null;
  longitude?: number | null;
  city?: string | null;
  location_confidence: number;
  entity_match_confidence: number;
  authenticity_score: number;
  geo_status: GeoStatus;
  matched_entity_id?: string | null;
  distance_km?: number | null;
  ambiguity_reason?: string | null;
  candidates?: GeoMatchCandidate[];
}

export interface GeocodeEntitiesResult {
  total_evaluated: number;
  resolved_count: number;
  unresolved_count: number;
  message: string;
  results: Array<{
    entity_id: string;
    name: string;
    status: string;
    latitude?: number;
    longitude?: number;
    location_source?: string;
    message?: string;
  }>;
}

export interface MapDataResponse {
  entities: MapEntityItem[];
  events: MapEventItem[];
  ambiguities_count: number;
  monitored_facilities_count?: number;
  geocoded_epicenters_count?: number;
  verified_matches_count?: number;
}

export interface GeoConfig {
  geolocation_enabled: boolean;
  require_location_verification: boolean;
  max_acceptable_distance_km: number;
  ambiguity_threshold: number;
  min_geo_confidence: number;
  geocoder_provider: string;
  cache_duration_seconds: number;
}

export type DeviceGPSStatus = 'AVAILABLE' | 'DENIED' | 'UNAVAILABLE' | 'ACQUIRING';

export interface UserDeviceLocation {
  latitude: number;
  longitude: number;
  accuracy_m: number;
  timestamp: string;
  status: DeviceGPSStatus;
}
