import React, { useEffect, useState } from 'react';
import {
  Globe,
  MapPin,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Crosshair,
  Layers,
  ArrowRight,
  CheckCircle2,
  AlertOctagon,
  Info,
} from 'lucide-react';
import { api } from '../api/client';
import { MapEntityItem, MapEventItem, MapDataResponse } from '../types/geo';
import { EnterpriseMap } from '../components/geo/EnterpriseMap';
import { IncidentDetailsModal } from '../components/incidents/IncidentDetailsModal';
import { DisruptionEvent } from '../types/events';

export const GeoIntelligencePage: React.FC = () => {
  const [mapData, setMapData] = useState<MapDataResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [isResolving, setIsResolving] = useState(false);
  const [resolutionStatus, setResolutionStatus] = useState<string | null>(null);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [modalEvent, setModalEvent] = useState<DisruptionEvent | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await api.getMapData();
      setMapData(data);
    } catch (err) {
      console.error('Failed to load map data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleResolveLocations = async () => {
    setIsResolving(true);
    setResolutionStatus('Resolving missing coordinates...');
    try {
      const res = await api.geocodeEntities();
      setResolutionStatus(res.message);
      await loadData();
      setTimeout(() => setResolutionStatus(null), 5000);
    } catch (err: any) {
      setResolutionStatus(err.message || 'Geocoding resolution failed');
      setTimeout(() => setResolutionStatus(null), 5000);
    } finally {
      setIsResolving(false);
    }
  };

  const [isSeeding, setIsSeeding] = useState(false);

  const handleSeedDemoData = async () => {
    setIsSeeding(true);
    try {
      await api.seedDemoGeoData();
      await loadData();
    } catch (err: any) {
      console.error('Failed to seed demo data', err);
    } finally {
      setIsSeeding(false);
    }
  };

  // Dynamically calculated KPI counts without hardcoded fallbacks
  const monitoredFacilities =
    mapData?.monitored_facilities_count ??
    (mapData?.entities ?? []).filter((e) => e.latitude != null && e.longitude != null).length;

  const geocodedDisruptions =
    mapData?.geocoded_epicenters_count ??
    (mapData?.events ?? []).filter((e) => e.latitude != null && e.longitude != null).length;

  const ambiguitiesCount =
    mapData?.ambiguities_count ??
    (mapData?.events ?? []).filter((e) => e.geo_status === 'LOCATION_AMBIGUOUS').length;

  const verifiedGeoMatches =
    mapData?.verified_matches_count ??
    (mapData?.events ?? []).filter(
      (e) => e.geo_status === 'LOCATION_VERIFIED' && e.matched_entity_id != null
    ).length;

  return (
    <div className="space-y-6">
      {/* Top Banner & Header */}
      <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#eeeef0] pb-4">
          <div className="space-y-1">
            <span className="text-[11px] font-mono uppercase tracking-wider text-[#6c47ff] font-semibold">
              STAGE 4 · GEOGRAPHIC INTELLIGENCE & DISAMBIGUATION
            </span>
            <h1 className="text-xl font-bold text-[#131316] flex items-center gap-2">
              <Globe className="w-5 h-5 text-[#6c47ff]" />
              <span>Real-Time GPS & Geospatial Entity Disambiguation Map</span>
            </h1>
            <p className="text-xs text-[#5e5f6e] max-w-3xl leading-relaxed">
              Differentiates facilities with identical names across distinct districts, states, and countries. Calculates Haversine distances, verifies administrative hierarchies, and halts downstream network propagation when locations are ambiguous.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={handleResolveLocations}
              disabled={isResolving || loading}
              className="btn-primary text-xs flex items-center gap-1.5"
              title="Geocodes business entities with missing coordinates via Nominatim"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isResolving ? 'animate-spin' : ''}`} />
              <span>{isResolving ? 'Resolving...' : resolutionStatus || 'Resolve Missing Locations'}</span>
            </button>

            {monitoredFacilities === 0 && (
              <button
                onClick={handleSeedDemoData}
                disabled={loading}
                className="btn-secondary text-xs flex items-center gap-1.5"
                title="Populates sample Gujarat supplier, factory, and warehouse facilities"
              >
                <Layers className="w-3.5 h-3.5 text-[#6c47ff]" />
                <span>Load Demo Gujarat Network</span>
              </button>
            )}

            <button
              onClick={loadData}
              disabled={loading}
              className="btn-secondary text-xs flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh Map Telemetry</span>
            </button>
          </div>
        </div>

        {/* 4 Dynamic KPI Cards Strip */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
          <div className="p-4 rounded-xl bg-[#f7f7f8] border border-[#d9d9de] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[#747686] block">
              Monitored Network Facilities
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-[#131316]">{monitoredFacilities}</span>
              <span className="text-xs text-[#747686]">geocoded nodes</span>
            </div>
            <span className="text-[11px] text-[#5e5f6e] block">Suppliers, factories, ports & warehouses</span>
          </div>

          <div className="p-4 rounded-xl bg-[#f7f7f8] border border-[#d9d9de] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[#747686] block">
              Geocoded Disruption Epicenters
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-[#6c47ff]">{geocodedDisruptions}</span>
              <span className="text-xs text-[#747686]">active</span>
            </div>
            <span className="text-[11px] text-emerald-700 font-medium block">
              {verifiedGeoMatches} verified with high confidence
            </span>
          </div>

          <div className="p-4 rounded-xl bg-amber-50/60 border border-amber-200 space-y-1">
            <span className="text-[10px] font-mono uppercase text-amber-800 font-semibold block">
              Location Ambiguities (Gated)
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-amber-800">{ambiguitiesCount}</span>
              <span className="text-xs text-amber-700">awaiting review</span>
            </div>
            <span className="text-[11px] text-amber-700 block">
              Network impact halted to prevent false links
            </span>
          </div>

          <div className="p-4 rounded-xl bg-[#f7f7f8] border border-[#d9d9de] space-y-1">
            <span className="text-[10px] font-mono uppercase text-[#747686] block">
              Verified Geo Matches
            </span>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold font-mono text-emerald-700">{verifiedGeoMatches}</span>
              <span className="text-xs text-[#747686]">matched facilities</span>
            </div>
            <span className="text-[11px] text-[#747686] block">
              OpenStreetMap + Nominatim rate-limited
            </span>
          </div>
        </div>
      </div>

      {/* Main Interactive Enterprise Map */}
      <EnterpriseMap
        entities={mapData?.entities ?? []}
        events={mapData?.events ?? []}
        selectedEventId={selectedEventId}
        onSelectEvent={(id) => setSelectedEventId(id)}
        onResolveLocations={handleResolveLocations}
        onSeedDemoData={handleSeedDemoData}
        isResolving={isResolving}
        isSeeding={isSeeding}
      />

      {/* Geospatial Intelligence Event Table */}
      <div className="bg-white border border-[#d9d9de] rounded-2xl shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between border-b border-[#eeeef0] pb-4">
          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-[#747686] block">
              Geospatial Telemetry Records
            </span>
            <h3 className="font-bold text-base text-[#131316]">
              Disruption Events & Geographic Matching Breakdown
            </h3>
          </div>
          <span className="text-xs text-[#747686]">
            Click any row to pinpoint on map or inspect multi-factor matching
          </span>
        </div>

        {(mapData?.events.length ?? 0) === 0 ? (
          <div className="py-12 text-center text-xs text-[#747686] space-y-2">
            <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
            <p className="font-semibold text-[#131316]">No active disruption locations currently tracked.</p>
            <p className="text-[11px] text-[#5e5f6e]">Trigger a monitoring scan to ingest fresh external signals.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-[#f7f7f8] text-[#5e5f6e] border-y border-[#d9d9de] uppercase font-mono text-[10px]">
                <tr>
                  <th className="py-2.5 px-3">Disruption Incident</th>
                  <th className="py-2.5 px-3">Reported Location</th>
                  <th className="py-2.5 px-3">Geo Status</th>
                  <th className="py-2.5 px-3">Location Conf</th>
                  <th className="py-2.5 px-3">Matched Entity</th>
                  <th className="py-2.5 px-3">Distance</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#eeeef0]">
                {(mapData?.events ?? []).map((evt) => {
                  const isAmbiguous = evt.geo_status === 'LOCATION_AMBIGUOUS';
                  const matchedEntity = mapData?.entities.find((e) => e.id === evt.matched_entity_id);

                  return (
                    <tr
                      key={evt.id}
                      onClick={() => setSelectedEventId(evt.id)}
                      className={`hover:bg-[#f7f7f8]/80 cursor-pointer transition-colors ${
                        selectedEventId === evt.id ? 'bg-violet-50/50' : ''
                      }`}
                    >
                      <td className="py-3 px-3 font-semibold text-[#131316] max-w-xs truncate">
                        {evt.headline}
                      </td>
                      <td className="py-3 px-3 font-mono text-[11px] text-[#5e5f6e]">
                        {evt.city || evt.location_mentioned || 'N/A'}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                            evt.geo_status === 'LOCATION_VERIFIED'
                              ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                              : isAmbiguous
                              ? 'bg-amber-100 text-amber-900 border border-amber-300'
                              : 'bg-slate-100 text-slate-800 border border-slate-300'
                          }`}
                        >
                          {evt.geo_status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono font-bold text-[#131316]">
                        {Math.round(evt.location_confidence)}%
                      </td>
                      <td className="py-3 px-3">
                        {isAmbiguous ? (
                          <span className="text-amber-800 font-semibold italic text-[11px]">
                            Review Required (Multiple candidates)
                          </span>
                        ) : matchedEntity ? (
                          <span className="font-semibold text-[#131316]">{matchedEntity.name}</span>
                        ) : (
                          <span className="text-[#747686]">Unassigned</span>
                        )}
                      </td>
                      <td className="py-3 px-3 font-mono text-[11px]">
                        {evt.distance_km != null ? (
                          <span className="text-[#6c47ff] font-bold">{evt.distance_km.toFixed(1)} km</span>
                        ) : (
                          <span className="text-[#747686]">N/A</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedEventId(evt.id);
                          }}
                          className="px-2.5 py-1 rounded bg-[#f7f7f8] hover:bg-[#eeeef0] text-[#131316] border border-[#d9d9de] text-[11px] font-medium"
                        >
                          Locate Pin
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Incident Details Modal if active */}
      {modalEvent && (
        <IncidentDetailsModal
          event={modalEvent}
          credibility={modalEvent.credibility}
          onClose={() => setModalEvent(null)}
        />
      )}
    </div>
  );
};
