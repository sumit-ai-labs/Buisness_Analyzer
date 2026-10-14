import React, { useState, useEffect } from 'react';
import { Database, Save, Settings as SettingsIcon, Sliders, ShieldCheck, Globe, MapPin } from 'lucide-react';
import { apiClient } from '../api/client';
import { SystemConfig } from '../types/risk';
import { GeoConfig } from '../types/geo';

export const SettingsPage: React.FC = () => {
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [geoConfig, setGeoConfig] = useState<GeoConfig>({
    geolocation_enabled: true,
    require_location_verification: true,
    max_acceptable_distance_km: 100.0,
    ambiguity_threshold: 0.15,
    min_geo_confidence: 0.50,
    geocoder_provider: 'nominatim',
    cache_duration_seconds: 86400,
  });
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    loadSettingsData();
  }, []);

  const loadSettingsData = async () => {
    try {
      setLoading(true);
      const [cfg, hlt, gCfg] = await Promise.all([
        apiClient.getSystemConfig(),
        apiClient.getHealth(),
        apiClient.getGeoConfig().catch(() => null),
      ]);
      setConfig(cfg);
      setHealth(hlt);
      if (gCfg) setGeoConfig(gCfg);
    } catch (err) {
      console.error('Failed to load settings:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;

    // Validate weights sum approximately to 1.0
    const sum =
      config.weights.dependency +
      config.weights.criticality +
      config.weights.lead_time +
      config.weights.single_source +
      config.weights.confidence;

    if (Math.abs(sum - 1.0) > 0.01) {
      alert(`Warning: The sum of risk factor weights is ${sum.toFixed(2)}. Weights should sum to 1.00 (100%).`);
      return;
    }

    try {
      setSaving(true);
      setMessage(null);
      await Promise.all([
        apiClient.updateSystemConfig(config),
        apiClient.updateGeoConfig(geoConfig).catch(() => null),
      ]);
      setMessage('System risk weights, classification thresholds, and Geographic Intelligence settings updated successfully!');
    } catch (err: any) {
      alert(err.message || 'Failed to update configuration.');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !config) {
    return <div className="p-12 text-center text-[#747686] text-xs">Loading configuration parameters...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-1">
        <div className="text-[11px] font-mono uppercase text-[#747686]">
          Risk Formula & Geographic Customization
        </div>
        <h1 className="text-xl font-bold tracking-tight text-[#131316] flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-[#6c47ff]" />
          <span>System Configuration & Intelligence Tuning</span>
        </h1>
        <p className="text-xs text-[#5e5f6e]">
          Customize risk factor scoring weights, classification threshold buckets, and geospatial entity disambiguation parameters.
        </p>
      </div>

      {message && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 text-xs flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{message}</span>
        </div>
      )}

      {/* Main Settings Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Customization Form */}
        <form onSubmit={handleSave} className="lg:col-span-2 space-y-6">
          {/* Factor Weights Card */}
          <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#131316] flex items-center gap-2">
              <Sliders className="w-4 h-4 text-[#6c47ff]" />
              <span>Risk Scoring Factor Weights (Must sum to 1.00)</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div>
                <div className="flex justify-between text-[#5e5f6e] mb-1">
                  <span>Dependency Weight ({Math.round(config.weights.dependency * 100)}%)</span>
                  <span className="text-[#6c47ff] font-mono font-bold">{config.weights.dependency.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.weights.dependency}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      weights: { ...config.weights, dependency: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full accent-[#6c47ff]"
                />
              </div>

              <div>
                <div className="flex justify-between text-[#5e5f6e] mb-1">
                  <span>Criticality Weight ({Math.round(config.weights.criticality * 100)}%)</span>
                  <span className="text-[#6c47ff] font-mono font-bold">{config.weights.criticality.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.weights.criticality}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      weights: { ...config.weights, criticality: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full accent-[#6c47ff]"
                />
              </div>

              <div>
                <div className="flex justify-between text-[#5e5f6e] mb-1">
                  <span>Lead Time Weight ({Math.round(config.weights.lead_time * 100)}%)</span>
                  <span className="text-[#6c47ff] font-mono font-bold">{config.weights.lead_time.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.weights.lead_time}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      weights: { ...config.weights, lead_time: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full accent-[#6c47ff]"
                />
              </div>

              <div>
                <div className="flex justify-between text-[#5e5f6e] mb-1">
                  <span>Single Source Vulnerability Weight ({Math.round(config.weights.single_source * 100)}%)</span>
                  <span className="text-[#6c47ff] font-mono font-bold">{config.weights.single_source.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.weights.single_source}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      weights: { ...config.weights, single_source: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full accent-[#6c47ff]"
                />
              </div>

              <div>
                <div className="flex justify-between text-[#5e5f6e] mb-1">
                  <span>Extraction Confidence Weight ({Math.round(config.weights.confidence * 100)}%)</span>
                  <span className="text-[#6c47ff] font-mono font-bold">{config.weights.confidence.toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.0"
                  step="0.05"
                  value={config.weights.confidence}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      weights: { ...config.weights, confidence: parseFloat(e.target.value) },
                    })
                  }
                  className="w-full accent-[#6c47ff]"
                />
              </div>
            </div>
          </div>

          {/* Classification Thresholds Card */}
          <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#131316] flex items-center gap-2">
              <Sliders className="w-4 h-4 text-[#6c47ff]" />
              <span>Risk Classification Threshold Buckets (0 - 100 Score)</span>
            </h3>

            <div className="grid grid-cols-3 gap-4 text-xs">
              <div>
                <label className="block text-[#5e5f6e] font-semibold mb-1">Low Max Score</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={config.thresholds.low}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      thresholds: { ...config.thresholds, low: parseFloat(e.target.value) || 0 },
                    })
                  }
                  className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                />
              </div>

              <div>
                <label className="block text-[#5e5f6e] font-semibold mb-1">Medium Max Score</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={config.thresholds.medium}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      thresholds: { ...config.thresholds, medium: parseFloat(e.target.value) || 0 },
                    })
                  }
                  className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                />
              </div>

              <div>
                <label className="block text-[#5e5f6e] font-semibold mb-1">High Max Score</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={config.thresholds.high}
                  onChange={(e) =>
                    setConfig({
                      ...config,
                      thresholds: { ...config.thresholds, high: parseFloat(e.target.value) || 0 },
                    })
                  }
                  className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                />
              </div>
            </div>
          </div>

          {/* Geographic Intelligence & Disambiguation Card */}
          <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#131316] flex items-center gap-2">
              <Globe className="w-4 h-4 text-[#6c47ff]" />
              <span>Geographic Intelligence & Location Disambiguation</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div className="flex items-center justify-between p-3 rounded-xl bg-[#f7f7f8] border border-[#eeeef0]">
                <div>
                  <span className="font-semibold text-[#131316] block">Require Location Verification</span>
                  <span className="text-[11px] text-[#747686]">
                    Halt NetworkX impact analysis when entity location cannot be confidently disambiguated.
                  </span>
                </div>
                <input
                  type="checkbox"
                  checked={geoConfig.require_location_verification}
                  onChange={(e) =>
                    setGeoConfig({ ...geoConfig, require_location_verification: e.target.checked })
                  }
                  className="w-4 h-4 accent-[#6c47ff] rounded cursor-pointer"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[#5e5f6e] font-semibold mb-1">
                    Max Acceptable Event Distance (km)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="1000"
                    value={geoConfig.max_acceptable_distance_km}
                    onChange={(e) =>
                      setGeoConfig({
                        ...geoConfig,
                        max_acceptable_distance_km: parseFloat(e.target.value) || 100,
                      })
                    }
                    className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                  />
                  <span className="text-[10px] text-[#747686] mt-0.5 block">Events farther than this are penalized in geo matching</span>
                </div>

                <div>
                  <label className="block text-[#5e5f6e] font-semibold mb-1">
                    Ambiguity Score Delta Threshold (%)
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="50"
                    value={Math.round(geoConfig.ambiguity_threshold * 100)}
                    onChange={(e) =>
                      setGeoConfig({
                        ...geoConfig,
                        ambiguity_threshold: (parseFloat(e.target.value) || 15) / 100.0,
                      })
                    }
                    className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                  />
                  <span className="text-[10px] text-[#747686] mt-0.5 block">Candidate score delta below which ambiguity is triggered</span>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[#5e5f6e] font-semibold mb-1">
                    Minimum Geo Confidence Required (%)
                  </label>
                  <input
                    type="number"
                    min="10"
                    max="95"
                    value={Math.round(geoConfig.min_geo_confidence * 100)}
                    onChange={(e) =>
                      setGeoConfig({
                        ...geoConfig,
                        min_geo_confidence: (parseFloat(e.target.value) || 50) / 100.0,
                      })
                    }
                    className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                  />
                </div>

                <div>
                  <label className="block text-[#5e5f6e] font-semibold mb-1">Geocoder Provider</label>
                  <select
                    value={geoConfig.geocoder_provider}
                    onChange={(e) => setGeoConfig({ ...geoConfig, geocoder_provider: e.target.value })}
                    className="w-full px-3 py-2 bg-white border border-[#d9d9de] rounded-lg text-[#131316] focus:outline-none focus:border-[#6c47ff]"
                  >
                    <option value="nominatim">OpenStreetMap Nominatim (Free / Normalized Cache)</option>
                    <option value="google_maps">Google Maps Geocoding (Configured in .env)</option>
                    <option value="mapbox">Mapbox Geocoding (Configured in .env)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={saving}
            className="btn-primary w-full py-3 text-xs"
          >
            <Save className="w-4 h-4" />
            <span>{saving ? 'Saving Settings...' : 'Save All Configurations'}</span>
          </button>
        </form>

        {/* Right Col: Integration Status Overview */}
        <div className="space-y-4">
          <div className="p-6 bg-white border border-[#d9d9de] rounded-2xl shadow-sm space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-[#131316] flex items-center gap-2">
              <Database className="w-4 h-4 text-[#6c47ff]" />
              <span>Integration Readiness</span>
            </h3>

            <div className="space-y-3 text-xs">
              <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
                <div className="flex items-center justify-between font-semibold text-[#131316]">
                  <span>FastAPI Backend</span>
                  <span className="text-emerald-700 font-mono">{health?.status || 'Unknown'}</span>
                </div>
                <p className="text-[11px] text-[#747686] mt-0.5">Environment: {health?.env || 'development'}</p>
              </div>

              <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
                <div className="flex items-center justify-between font-semibold text-[#131316]">
                  <span>Geocoding & Haversine Engine</span>
                  <span className="text-emerald-700 font-mono">Active (Nominatim)</span>
                </div>
                <p className="text-[11px] text-[#747686] mt-0.5">Pre-seeded cache: 12 key enterprise global hubs</p>
              </div>

              <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
                <div className="flex items-center justify-between font-semibold text-[#131316]">
                  <span>Tavily Research Key</span>
                  {health?.tavily_key_configured ? (
                    <span className="text-emerald-700 font-mono">Configured</span>
                  ) : (
                    <span className="text-amber-700 font-mono">Simulated / Fallback</span>
                  )}
                </div>
                <p className="text-[11px] text-[#747686] mt-0.5">TAVILY_API_KEY in backend/.env</p>
              </div>

              <div className="p-3 rounded-xl bg-[#f7f7f8] border border-[#d9d9de]">
                <div className="flex items-center justify-between font-semibold text-[#131316]">
                  <span>LLM Extraction Engine</span>
                  {health?.llm_key_configured ? (
                    <span className="text-emerald-700 font-mono">{health?.llm_provider?.toUpperCase()}</span>
                  ) : (
                    <span className="text-[#6c47ff] font-mono">Heuristic Active</span>
                  )}
                </div>
                <p className="text-[11px] text-[#747686] mt-0.5">LLM_API_KEY in backend/.env</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
