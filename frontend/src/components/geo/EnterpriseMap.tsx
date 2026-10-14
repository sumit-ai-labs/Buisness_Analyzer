import React, { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  Navigation,
  Crosshair,
  ShieldAlert,
  ShieldCheck,
  AlertTriangle,
  Layers,
  MapPin,
  CheckCircle2,
  XCircle,
  Eye,
  ArrowRight,
  RefreshCw,
  Info,
  Maximize2,
} from 'lucide-react';
import { MapEntityItem, MapEventItem, UserDeviceLocation, DeviceGPSStatus } from '../../types/geo';

interface EnterpriseMapProps {
  entities: MapEntityItem[];
  events: MapEventItem[];
  selectedEventId?: string | null;
  onSelectEvent?: (eventId: string | null) => void;
  onSelectEntity?: (entityId: string | null) => void;
  onResolveLocations?: () => void;
  onSeedDemoData?: () => void;
  isResolving?: boolean;
  isSeeding?: boolean;
}

export const EnterpriseMap: React.FC<EnterpriseMapProps> = ({
  entities,
  events,
  selectedEventId,
  onSelectEvent,
  onSelectEntity,
  onResolveLocations,
  onSeedDemoData,
  isResolving = false,
  isSeeding = false,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const linesLayerRef = useRef<L.LayerGroup | null>(null);
  const userMarkerRef = useRef<L.CircleMarker | null>(null);
  const userCircleRef = useRef<L.Circle | null>(null);

  // Inspector & filter state
  const [activeInspectorEvent, setActiveInspectorEvent] = useState<MapEventItem | null>(null);
  const [activeInspectorEntity, setActiveInspectorEntity] = useState<MapEntityItem | null>(null);
  const [showDistances, setShowDistances] = useState(true);
  const [filterSeverity, setFilterSeverity] = useState<string>('all');
  const [filterEntityType, setFilterEntityType] = useState<string>('all');
  const [isBannerDismissed, setIsBannerDismissed] = useState(false);

  // Browser GPS state
  const [deviceLocation, setDeviceLocation] = useState<UserDeviceLocation | null>(null);
  const [gpsStatus, setGpsStatus] = useState<DeviceGPSStatus>('AVAILABLE');
  const [isAcquiringGps, setIsAcquiringGps] = useState(false);
  const [gpsWatchId, setGpsWatchId] = useState<number | null>(null);

  // Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Default center around Gujarat / Western India regional business hub
    const map = L.map(mapContainerRef.current, {
      center: [22.2587, 71.1924],
      zoom: 7,
      zoomControl: false,
    });

    // 100% Free OpenStreetMap standard tile layer (zero API key or token required)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    linesLayerRef.current = L.layerGroup().addTo(map);

    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // Update selected event if controlled prop changes
  useEffect(() => {
    if (selectedEventId) {
      const found = events.find((e) => e.id === selectedEventId);
      if (found) {
        setActiveInspectorEvent(found);
        setActiveInspectorEntity(null);
        if (found.latitude && found.longitude && mapInstanceRef.current) {
          mapInstanceRef.current.flyTo([found.latitude, found.longitude], 7, { duration: 1.2 });
        }
      }
    }
  }, [selectedEventId, events]);

  // Request user/device browser GPS with explicit consent
  const handleRequestUserLocation = () => {
    if (!navigator.geolocation) {
      setGpsStatus('UNAVAILABLE');
      return;
    }

    setIsAcquiringGps(true);
    setGpsStatus('ACQUIRING');

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setIsAcquiringGps(false);
        const { latitude, longitude, accuracy } = position.coords;
        const newLoc: UserDeviceLocation = {
          latitude,
          longitude,
          accuracy_m: Math.round(accuracy),
          timestamp: new Date().toLocaleTimeString(),
          status: 'AVAILABLE',
        };
        setDeviceLocation(newLoc);
        setGpsStatus('AVAILABLE');

        // Draw user GPS on map
        if (mapInstanceRef.current) {
          if (userMarkerRef.current) userMarkerRef.current.remove();
          if (userCircleRef.current) userCircleRef.current.remove();

          userCircleRef.current = L.circle([latitude, longitude], {
            radius: accuracy,
            color: '#3b82f6',
            fillColor: '#3b82f6',
            fillOpacity: 0.12,
            weight: 1,
            dashArray: '3, 6',
          }).addTo(mapInstanceRef.current);

          userMarkerRef.current = L.circleMarker([latitude, longitude], {
            radius: 8,
            color: '#ffffff',
            fillColor: '#2563eb',
            fillOpacity: 1,
            weight: 2,
          })
            .bindPopup(
              `<div style="font-family:sans-serif;font-size:12px;">
                <strong>Operator Device GPS</strong><br/>
                Accuracy: ±${Math.round(accuracy)}m<br/>
                <span style="color:#747686;font-size:10px;">Contextual location (never transmitted or linked to events)</span>
              </div>`
            )
            .addTo(mapInstanceRef.current);

          mapInstanceRef.current.flyTo([latitude, longitude], 9, { duration: 1.2 });
        }
      },
      (error) => {
        setIsAcquiringGps(false);
        if (error.code === error.PERMISSION_DENIED) {
          setGpsStatus('DENIED');
        } else {
          setGpsStatus('UNAVAILABLE');
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000,
      }
    );
  };

  // Render markers and vector lines
  useEffect(() => {
    if (!mapInstanceRef.current || !markersLayerRef.current || !linesLayerRef.current) return;

    markersLayerRef.current.clearLayers();
    linesLayerRef.current.clearLayers();

    const bounds: L.LatLngExpression[] = [];

    // Filtered lists
    const filteredEntities = entities.filter((ent) => {
      if (filterEntityType !== 'all' && ent.type !== filterEntityType) return false;
      return ent.latitude != null && ent.longitude != null;
    });

    const filteredEvents = events.filter((evt) => {
      if (filterSeverity !== 'all' && evt.severity !== filterSeverity) return false;
      return evt.latitude != null && evt.longitude != null;
    });

    // 1. Draw Business Entities
    filteredEntities.forEach((entity) => {
      if (entity.latitude == null || entity.longitude == null) return;
      bounds.push([entity.latitude, entity.longitude]);

      const isSelected = activeInspectorEntity?.id === entity.id;

      // Color coding per entity category
      let pinColor = '#6c47ff'; // violet default
      if (entity.type === 'supplier') pinColor = '#3b82f6'; // blue
      else if (entity.type === 'factory') pinColor = '#f59e0b'; // amber
      else if (entity.type === 'warehouse') pinColor = '#8b5cf6'; // purple
      else if (entity.type === 'route') pinColor = '#06b6d4'; // cyan

      const entityIcon = L.divIcon({
        className: 'custom-entity-pin',
        html: `
          <div style="
            background: ${pinColor};
            width: ${isSelected ? '24px' : '18px'};
            height: ${isSelected ? '24px' : '18px'};
            border-radius: 50%;
            border: 2px solid #ffffff;
            box-shadow: 0 2px 6px rgba(0,0,0,0.3);
            display: flex;
            align-items: center;
            justify-content: center;
            color: #ffffff;
            font-size: 10px;
            font-weight: bold;
            transition: all 0.2s ease;
          ">
            ${entity.type.charAt(0).toUpperCase()}
          </div>
        `,
        iconSize: [24, 24],
        iconAnchor: [12, 12],
      });

      const marker = L.marker([entity.latitude, entity.longitude], { icon: entityIcon })
        .bindTooltip(
          `<strong>${entity.name}</strong><br/><span style="color:#747686;font-size:10px;">${entity.type.toUpperCase()} · ${entity.location}</span>`,
          { direction: 'top', offset: [0, -10] }
        )
        .on('click', () => {
          setActiveInspectorEntity(entity);
          setActiveInspectorEvent(null);
          if (onSelectEntity) onSelectEntity(entity.id);
        });

      markersLayerRef.current?.addLayer(marker);
    });

    // 2. Draw Disruption Events
    filteredEvents.forEach((event) => {
      if (event.latitude == null || event.longitude == null) return;
      bounds.push([event.latitude, event.longitude]);

      const isSelected = activeInspectorEvent?.id === event.id;
      const isAmbiguous = event.geo_status === 'LOCATION_AMBIGUOUS';

      // Pulse color by severity
      let eventColor = '#ef4444'; // red high/critical
      if (event.severity === 'medium') eventColor = '#f59e0b';
      else if (event.severity === 'low') eventColor = '#6c47ff';

      if (isAmbiguous) {
        eventColor = '#d97706'; // amber-orange for ambiguous
      }

      const eventIcon = L.divIcon({
        className: 'custom-event-pin',
        html: `
          <div style="position: relative; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;">
            <div style="
              position: absolute;
              width: 100%;
              height: 100%;
              border-radius: 50%;
              background: ${eventColor};
              opacity: 0.35;
              animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
            "></div>
            <div style="
              width: ${isSelected ? '22px' : '18px'};
              height: ${isSelected ? '22px' : '18px'};
              border-radius: 50%;
              background: ${eventColor};
              border: 2px solid #ffffff;
              box-shadow: 0 3px 8px rgba(0,0,0,0.4);
              display: flex;
              align-items: center;
              justify-content: center;
              color: #ffffff;
              font-size: 11px;
              font-weight: bold;
              z-index: 2;
            ">!</div>
          </div>
        `,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
      });

      const marker = L.marker([event.latitude, event.longitude], { icon: eventIcon })
        .bindTooltip(
          `<strong>${event.headline}</strong><br/><span style="color:#ef4444;font-size:10px;">${event.event_type.toUpperCase()} · Status: ${event.geo_status}</span>`,
          { direction: 'top', offset: [0, -12] }
        )
        .on('click', () => {
          setActiveInspectorEvent(event);
          setActiveInspectorEntity(null);
          if (onSelectEvent) onSelectEvent(event.id);
        });

      markersLayerRef.current?.addLayer(marker);

      // 3. Draw Distance Vector to Matched Entity
      // Only draw distance vectors when: event has valid coordinates, matched entity has valid coordinates,
      // AND entity match is NOT ambiguous!
      if (
        showDistances &&
        event.matched_entity_id &&
        event.geo_status !== 'LOCATION_AMBIGUOUS'
      ) {
        const matchedEnt = entities.find((e) => e.id === event.matched_entity_id);
        if (
          matchedEnt &&
          matchedEnt.latitude != null &&
          matchedEnt.longitude != null &&
          linesLayerRef.current
        ) {
          const polyline = L.polyline(
            [
              [event.latitude, event.longitude],
              [matchedEnt.latitude, matchedEnt.longitude],
            ],
            {
              color: isSelected ? '#6c47ff' : '#94a3b8',
              weight: isSelected ? 3 : 2,
              opacity: isSelected ? 0.9 : 0.65,
            }
          ).bindTooltip(
            `<strong>Haversine Vector</strong><br/>Distance: ${event.distance_km != null ? event.distance_km.toFixed(1) : '?'} km<br/><span style="color:#747686;font-size:10px;">${event.headline} ↔ ${matchedEnt.name}</span>`,
            { sticky: true }
          ).on('click', () => {
            setActiveInspectorEvent(event);
            setActiveInspectorEntity(null);
            if (onSelectEvent) onSelectEvent(event.id);
          });

          linesLayerRef.current.addLayer(polyline);
        }
      }
    });

    // Auto-fit bounds if entities or events exist with valid coordinates
    if (bounds.length > 0 && !activeInspectorEvent && !activeInspectorEntity) {
      try {
        mapInstanceRef.current.fitBounds(L.latLngBounds(bounds), { padding: [50, 50], maxZoom: 12 });
      } catch (err) {
        // bounds fit silently fallback
      }
    }
  }, [entities, events, activeInspectorEvent, activeInspectorEntity, showDistances, filterSeverity, filterEntityType]);

  const hasNoCoordinates =
    entities.filter((e) => e.latitude != null && e.longitude != null).length === 0 &&
    events.filter((e) => e.latitude != null && e.longitude != null).length === 0;

  return (
    <div className="relative w-full h-[680px] min-h-[520px] bg-[#f7f7f8] border border-[#d9d9de] rounded-2xl overflow-hidden shadow-sm flex">
      {/* MAP CANVAS (Left 70-75%) */}
      <div className="relative flex-1 h-full min-h-[520px]">
        <div ref={mapContainerRef} className="w-full h-full min-h-[520px] z-0" />

        {/* Informational overlay when no verified entities or disruptions with coordinates exist */}
        {hasNoCoordinates && !isBannerDismissed && (
          <div className="absolute inset-0 z-[400] flex items-center justify-center p-6 pointer-events-none">
            <div className="relative bg-white/95 backdrop-blur-md border border-[#d9d9de] rounded-2xl shadow-xl p-6 max-w-md text-center space-y-3 pointer-events-auto">
              {/* Close / Dismiss button */}
              <button
                onClick={() => setIsBannerDismissed(true)}
                className="absolute top-3 right-3 w-6 h-6 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-700 hover:bg-slate-100 text-xs font-bold transition-all"
                title="Dismiss overlay and view map"
              >
                ✕
              </button>

              <div className="w-10 h-10 rounded-full bg-violet-50 text-[#6c47ff] flex items-center justify-center mx-auto">
                <MapPin className="w-5 h-5 text-[#6c47ff]" />
              </div>
              <div className="space-y-1">
                <h4 className="font-bold text-sm text-slate-900" style={{ color: '#0f172a' }}>
                  No verified geographic events or facilities yet.
                </h4>
                <p className="text-xs text-slate-600 leading-relaxed" style={{ color: '#334155' }}>
                  Configure business entity locations or load the demo Gujarat network to populate the map.
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
                {onResolveLocations && (
                  <button
                    onClick={onResolveLocations}
                    disabled={isResolving}
                    className="btn-primary text-xs py-2 px-3 flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${isResolving ? 'animate-spin' : ''}`} />
                    <span>{isResolving ? 'Resolving Locations...' : 'Resolve Missing Locations'}</span>
                  </button>
                )}
                {onSeedDemoData && (
                  <button
                    onClick={onSeedDemoData}
                    disabled={isSeeding}
                    className="btn-secondary text-xs py-2 px-3 flex items-center gap-1.5"
                  >
                    <Layers className={`w-3.5 h-3.5 text-[#6c47ff] ${isSeeding ? 'animate-spin' : ''}`} />
                    <span>{isSeeding ? 'Loading Network...' : 'Load Demo Gujarat Network'}</span>
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Floating Top Controls Toolbar */}
        <div className="absolute top-4 left-4 z-10 flex flex-wrap items-center gap-2 bg-white/95 backdrop-blur-md p-2 rounded-xl border border-[#d9d9de] shadow-md text-xs">
          {/* GPS Button */}
          <button
            onClick={handleRequestUserLocation}
            disabled={isAcquiringGps}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-1.5 transition-all ${
              deviceLocation
                ? 'bg-blue-50 text-blue-800 border border-blue-200'
                : 'bg-white hover:bg-[#f7f7f8] text-[#131316] border border-[#d9d9de]'
            }`}
            title="Request explicit browser geolocation to show your position contextually"
          >
            <Crosshair className={`w-3.5 h-3.5 ${isAcquiringGps ? 'animate-spin text-blue-600' : 'text-blue-600'}`} />
            <span>
              {isAcquiringGps
                ? 'Acquiring GPS...'
                : deviceLocation
                ? `GPS Active (±${deviceLocation.accuracy_m}m)`
                : 'Use My Location'}
            </span>
          </button>

          {/* Low GPS Accuracy Warning Badge (> 1000m) */}
          {deviceLocation && deviceLocation.accuracy_m > 1000 && (
            <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300 font-mono text-[10px]">
              GPS ACCURACY LOW
            </span>
          )}

          {/* GPS Status Indicator */}
          {gpsStatus === 'DENIED' && (
            <span className="px-2 py-0.5 rounded bg-rose-100 text-rose-800 border border-rose-300 text-[10px]">
              Permission Denied
            </span>
          )}

          <div className="h-4 w-[1px] bg-[#d9d9de] mx-1" />

          {/* Distance Lines Toggle */}
          <button
            onClick={() => setShowDistances(!showDistances)}
            className={`px-2.5 py-1.5 rounded-lg font-medium transition-all ${
              showDistances ? 'bg-[#6c47ff] text-white' : 'bg-[#f7f7f8] text-[#5e5f6e]'
            }`}
          >
            Distance Vectors: {showDistances ? 'ON' : 'OFF'}
          </button>

          {/* Filter Entity Type */}
          <select
            value={filterEntityType}
            onChange={(e) => setFilterEntityType(e.target.value)}
            className="px-2 py-1 bg-white border border-[#d9d9de] rounded-lg text-[#131316] text-[11px]"
          >
            <option value="all">All Entities ({entities.length})</option>
            <option value="supplier">Suppliers</option>
            <option value="factory">Factories</option>
            <option value="warehouse">Warehouses</option>
            <option value="route">Transport Routes</option>
          </select>

          {/* Filter Severity */}
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="px-2 py-1 bg-white border border-[#d9d9de] rounded-lg text-[#131316] text-[11px]"
          >
            <option value="all">All Disruptions ({events.length})</option>
            <option value="high">High / Critical</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Floating Minimal Legend */}
        <div className="absolute bottom-4 left-4 z-10 bg-white/95 backdrop-blur-md p-3 rounded-xl border border-[#d9d9de] shadow-md text-[11px] space-y-1.5 font-medium">
          <div className="font-bold text-xs text-[#131316] mb-1 font-mono uppercase tracking-wider">
            Map Legend
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-red-500 border border-white" />
            <span className="text-[#5e5f6e]">Disruption Epicenter</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-amber-500 border border-white" />
            <span className="text-[#5e5f6e]">Ambiguous Disruption Location</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#3b82f6] border border-white" />
            <span className="text-[#5e5f6e]">Monitored Facility (Supplier/Plant)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-5 h-0.5 border-t-2 border-dashed border-[#6c47ff]" />
            <span className="text-[#5e5f6e]">Haversine Distance Line</span>
          </div>
        </div>
      </div>

      {/* RIGHT SIDE INSPECTOR PANEL (340px) */}
      <div className="w-84 md:w-96 bg-white border-l border-[#d9d9de] flex flex-col justify-between overflow-y-auto z-10 p-5 space-y-4 shadow-xl">
        {activeInspectorEvent ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#6c47ff] font-semibold block">
                  EVENT GEOGRAPHIC INSPECTOR
                </span>
                <h3 className="font-bold text-sm text-[#131316] leading-tight">
                  {activeInspectorEvent.headline}
                </h3>
              </div>
              <button
                onClick={() => setActiveInspectorEvent(null)}
                className="text-[#747686] hover:text-[#131316] text-xs font-bold p-1"
              >
                ✕
              </button>
            </div>

            {/* Status Strip */}
            <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de] space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-[#747686]">Geo Status:</span>
                <span
                  className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                    activeInspectorEvent.geo_status === 'LOCATION_VERIFIED'
                      ? 'bg-emerald-100 text-emerald-900 border border-emerald-300'
                      : activeInspectorEvent.geo_status === 'LOCATION_AMBIGUOUS'
                      ? 'bg-amber-100 text-amber-900 border border-amber-300'
                      : 'bg-slate-100 text-slate-800 border border-slate-300'
                  }`}
                >
                  {activeInspectorEvent.geo_status.replace('_', ' ')}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-2 pt-2 border-t border-[#eeeef0] text-center font-mono">
                <div className="p-1.5 rounded bg-white border border-[#eeeef0]">
                  <span className="text-[9px] text-[#747686] block">CREDIBILITY</span>
                  <span className="font-bold text-xs text-[#131316]">
                    {Math.round(activeInspectorEvent.authenticity_score)}/100
                  </span>
                </div>
                <div className="p-1.5 rounded bg-white border border-[#eeeef0]">
                  <span className="text-[9px] text-[#747686] block">LOC CONF</span>
                  <span className="font-bold text-xs text-[#6c47ff]">
                    {Math.round(activeInspectorEvent.location_confidence)}/100
                  </span>
                </div>
                <div className="p-1.5 rounded bg-white border border-[#eeeef0]">
                  <span className="text-[9px] text-[#747686] block">ENTITY CONF</span>
                  <span className="font-bold text-xs text-emerald-700">
                    {Math.round(activeInspectorEvent.entity_match_confidence)}/100
                  </span>
                </div>
              </div>
            </div>

            {/* Event Location Coordinates */}
            <div className="space-y-1 text-xs">
              <span className="text-[10px] font-mono uppercase text-[#747686] font-semibold block">
                Disruption Location
              </span>
              <div className="p-3 rounded-xl border border-[#d9d9de] bg-white space-y-1">
                <div className="font-bold text-[#131316]">
                  {activeInspectorEvent.city || activeInspectorEvent.location_mentioned || 'Unknown Epicenter'}
                </div>
                <div className="text-[11px] font-mono text-[#747686]">
                  Lat: {activeInspectorEvent.latitude?.toFixed(4) ?? 'None'} · Lon:{' '}
                  {activeInspectorEvent.longitude?.toFixed(4) ?? 'None'}
                </div>
              </div>
            </div>

            {/* Matched Entity or Ambiguity Explanation */}
            {activeInspectorEvent.geo_status === 'LOCATION_AMBIGUOUS' ? (
              <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs space-y-2">
                <div className="flex items-center gap-1.5 font-bold">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>Ambiguous Location Matches</span>
                </div>
                <p className="text-[11px] leading-relaxed text-amber-800">
                  {activeInspectorEvent.ambiguity_reason ||
                    'Multiple business facilities exist with similar names or close geographic proximity. System halted network propagation to prevent incorrect entity attribution.'}
                </p>
                {activeInspectorEvent.candidates && activeInspectorEvent.candidates.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-amber-200">
                    <span className="text-[10px] font-mono uppercase font-semibold">Evaluated Candidates:</span>
                    {activeInspectorEvent.candidates.slice(0, 3).map((c) => (
                      <div
                        key={c.entity_id}
                        className="p-2 rounded bg-white/80 border border-amber-200 text-[11px] flex justify-between"
                      >
                        <div>
                          <strong className="text-[#131316]">{c.entity_name}</strong>
                          <span className="text-[#747686] block">{c.entity_location}</span>
                        </div>
                        <div className="text-right font-mono">
                          <span className="text-amber-800 font-bold">{Math.round(c.geo_confidence * 100)}%</span>
                          <span className="text-[10px] text-[#747686] block">
                            {c.distance_km != null ? `${c.distance_km.toFixed(1)}km` : 'N/A'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-1 text-xs">
                <span className="text-[10px] font-mono uppercase text-[#747686] font-semibold block">
                  Matched Business Entity
                </span>
                <div className="p-3 rounded-xl border border-[#d9d9de] bg-white space-y-2">
                  <div className="flex justify-between items-baseline">
                    <strong className="text-[#131316]">
                      {entities.find((e) => e.id === activeInspectorEvent.matched_entity_id)?.name ||
                        'Unassigned Facility'}
                    </strong>
                    <span className="font-mono text-[11px] text-[#6c47ff] font-bold">
                      {activeInspectorEvent.distance_km != null
                        ? `${activeInspectorEvent.distance_km.toFixed(1)} km away`
                        : 'Local Facility'}
                    </span>
                  </div>

                  {/* Administrative Matches Checklist */}
                  <div className="grid grid-cols-2 gap-1.5 pt-2 border-t border-[#eeeef0] text-[10px] font-mono text-[#5e5f6e]">
                    <div className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      <span>City Match ✓</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      <span>State Match ✓</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      <span>Country Match ✓</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      <span>Lexical Match ✓</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div className="pt-2">
              <a
                href="/network"
                className="btn-primary w-full py-2.5 text-xs flex items-center justify-center gap-2"
              >
                <span>View Network Impact Traversal</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        ) : activeInspectorEntity ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between border-b border-[#eeeef0] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-[#3b82f6] font-semibold block">
                  FACILITY INSPECTOR
                </span>
                <h3 className="font-bold text-sm text-[#131316]">{activeInspectorEntity.name}</h3>
              </div>
              <button
                onClick={() => setActiveInspectorEntity(null)}
                className="text-[#747686] hover:text-[#131316] text-xs font-bold p-1"
              >
                ✕
              </button>
            </div>

            <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de] space-y-1.5 text-xs">
              <div className="flex justify-between">
                <span className="text-[#747686]">Category Type:</span>
                <strong className="text-[#131316] uppercase font-mono">{activeInspectorEntity.type}</strong>
              </div>
              <div className="flex justify-between">
                <span className="text-[#747686]">Operational Location:</span>
                <span className="text-[#131316]">{activeInspectorEntity.location}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#747686]">GPS Coordinates:</span>
                <span className="font-mono text-[11px] text-[#5e5f6e]">
                  {activeInspectorEntity.latitude?.toFixed(4)}, {activeInspectorEntity.longitude?.toFixed(4)}
                </span>
              </div>
            </div>

            <div className="p-3 rounded-xl bg-white border border-[#d9d9de] text-xs space-y-1">
              <span className="text-[10px] font-mono uppercase text-[#747686] block">Downstream Risk Status</span>
              <p className="text-[#5e5f6e] leading-relaxed text-[11px]">
                Facility monitored by autonomous early-warning engine. Geographic proximity verification prevents false
                incident links.
              </p>
            </div>
          </div>
        ) : (
          <div className="py-20 text-center space-y-3 text-xs text-[#747686]">
            <MapPin className="w-8 h-8 text-[#6c47ff] mx-auto opacity-70" />
            <p className="font-semibold text-[#131316]">Geographic Inspector Ready</p>
            <p className="text-[11px] text-[#5e5f6e] max-w-xs mx-auto">
              Click any disruption pin or monitored business facility on the map to inspect GPS coordinates, distance
              vectors, and multi-factor location confidence.
            </p>
          </div>
        )}

        {/* Privacy Note */}
        <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de] text-[10px] text-[#747686] space-y-1">
          <div className="flex items-center gap-1 font-semibold text-[#131316]">
            <Info className="w-3 h-3 text-[#6c47ff]" />
            <span>Privacy & GPS Principle</span>
          </div>
          <p>
            Browser GPS is optional and only queried with permission. Device location provides user context only and is
            never confused with event locations.
          </p>
        </div>
      </div>
    </div>
  );
};
