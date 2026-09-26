import React, { useState, useEffect } from 'react';
import {
  Zap,
  AlertTriangle,
  RefreshCw,
  BarChart2,
  Settings,
  Activity,
  ChevronRight,
  ChevronDown,
  RotateCcw,
  CloudRain,
  MapPin,
  FileText,
  Info
} from 'lucide-react';
import RecoveryTimeline from './RecoveryTimeline';
import { apiFetch } from '../api';

export default function ControlPanel({
  scenario,
  scenarioId,
  config,
  setConfig,
  onGenerate,
  onOptimize,
  onSimulateIncident,
  onReOptimize,
  onReplay,
  onRunBenchmark,
  loading,
  statusState,
  networkState,
  incidentInfo,
  currentResult,
  timeline,
  conditionMeta,
  trafficMode = 'normal',
  weatherEnabled = false,
  conditionsDirty = false,
  onApplyConditions,
  networkSource = 'synthetic',
  setNetworkSource,
  place = '',
  setPlace,
  radiusM = 1200,
  setRadiusM,
  networkMeta,
  manifest
}) {
  // Demo state-machine guards: an incident can't be simulated before there's
  // an optimized route to disrupt, and re-optimization is meaningless before
  // something has actually changed the scenario's edge costs - either an
  // incident or an environmental condition change.
  const canSimulateIncident = Boolean(currentResult) && !loading;
  const canReOptimize = Boolean(incidentInfo || conditionsDirty) && !loading;
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleConfigChange = (key, value) => {
    setConfig(prev => ({
      ...prev,
      [key]: value
    }));
  };

  const handleWeightChange = (key, value) => {
    setConfig(prev => ({
      ...prev,
      weights: {
        ...prev.weights,
        [key]: value
      }
    }));
  };

  // Live objective-weight preview: re-scores the *already-computed* current
  // routes against the in-progress weight edits via the backend evaluator
  // (POST /api/evaluate) - never computed here in the frontend. Debounced
  // so it doesn't fire on every keystroke, and it never triggers a
  // re-optimization; the real routes only change on an explicit Optimize.
  const [previewCost, setPreviewCost] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  useEffect(() => {
    if (!currentResult?.routes?.length || !scenarioId) {
      setPreviewCost(null);
      return;
    }
    setPreviewLoading(true);
    const timer = setTimeout(() => {
      apiFetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: scenarioId,
          routes: currentResult.routes,
          weights: config.weights
        })
      })
        .then(res => (res.ok ? res.json() : null))
        .then(data => { if (data) setPreviewCost(data.total_cost); })
        .catch(() => {})
        .finally(() => setPreviewLoading(false));
    }, 400);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.weights, currentResult, scenarioId]);

  // Scenario Health Strip - every field reads directly from real
  // scenario/state data already held by App.jsx, nothing invented here.
  const hasCongestion = scenario?.edges?.some(e => e.traffic_factor > 1.0) || false;
  const healthLabel = networkState === 'DISRUPTED' ? 'DISRUPTED'
    : networkState === 'RE-OPTIMIZED' ? 'RE-OPTIMIZED'
    : currentResult ? 'OPTIMIZED'
    : 'READY';

  return (
    <div className="clean-panel p-3.5 rounded-xl space-y-3 border border-[#332E29] text-xs shadow-xl w-full h-full flex flex-col">
      {/* 1. ESSENTIAL SECTION */}
      <div className="space-y-2">
        {scenario && (
          <div className="font-mono text-gray-300 mb-2 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px]">
            <span>{scenario.vehicles?.length || 0} Vehicles</span>
            <span className="text-gray-600">·</span>
            <span>{scenario.edges?.length || 0} Road Segments</span>
            <span className="text-gray-600">·</span>
            <span>{scenario.jobs?.length || 0} Delivery Points</span>
            <span className="text-gray-600">·</span>
            <span
              className={hasCongestion ? 'text-[#E8A93A]' : 'text-[#6B9A57]'}
              title="Simulated congestion from the traffic model - not a live traffic feed"
            >
              Sim. Traffic: {hasCongestion ? 'Congested' : 'Free flow'}
            </span>
            <span className="text-gray-600">·</span>
            <span className="text-[#C6602E] font-bold">{healthLabel}</span>
          </div>
        )}

        {/* Network source. The OSM path is the backend's existing
            Nominatim -> Overpass chain; nothing about the network is
            constructed here. */}
        <div className="bg-[#141210]/50 border border-[#332E29] rounded-lg p-2.5 space-y-2">
          <div className="flex items-center gap-1.5 text-gray-300 font-semibold uppercase tracking-wider text-[10px]">
            <MapPin size={12} className="text-[#5D7A9E]" />
            Road Network
          </div>

          <div className="grid grid-cols-2 gap-1">
            {[
              { id: 'synthetic', label: 'Synthetic' },
              { id: 'osm', label: 'OpenStreetMap' }
            ].map(opt => (
              <button
                key={opt.id}
                onClick={() => setNetworkSource?.(opt.id)}
                disabled={loading}
                aria-pressed={networkSource === opt.id}
                className={`px-2 py-1 rounded border text-[10px] transition-colors disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-[#5D7A9E] ${
                  networkSource === opt.id
                    ? 'bg-[#1E2A33] border-[#2E4A56] text-[#8FBAC9]'
                    : 'bg-[#26221D] border-[#3A342E] text-gray-400 hover:text-gray-200'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {networkSource === 'osm' && (
            <div className="space-y-1.5">
              <label htmlFor="osm-place" className="text-gray-400 block text-[10px]">
                Location (any place name, geocoded by Nominatim)
              </label>
              <input
                id="osm-place"
                type="text"
                value={place}
                placeholder="e.g. Hazratganj, Lucknow"
                onChange={(e) => setPlace?.(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && place.trim()) onGenerate?.('osm'); }}
                className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-1 outline-none focus:border-[#5D7A9E] focus-visible:ring-2 focus-visible:ring-[#5D7A9E] text-[10px]"
              />
              <div className="flex items-center gap-2">
                <label htmlFor="osm-radius" className="text-gray-400 text-[10px] flex-shrink-0">Radius (m)</label>
                <input
                  id="osm-radius"
                  type="number"
                  min="200"
                  step="100"
                  value={radiusM}
                  onChange={(e) => setRadiusM?.(Number(e.target.value))}
                  className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-0.5 outline-none focus:border-[#5D7A9E] font-mono text-[10px]"
                />
              </div>
              <button
                onClick={() => onGenerate?.('osm')}
                disabled={loading || !place.trim()}
                className="w-full py-1.5 bg-[#1E2A33]/60 border border-[#2E4A56] text-[#8FBAC9] hover:bg-[#1E2A33] rounded text-[11px] transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#5D7A9E]"
              >
                Load Real Road Network
              </button>
              <p className="text-[9px] text-gray-600 leading-snug">
                OpenStreetMap supplies roads, geometry, one-way rules and speed limits only.
                It carries no traffic data. If the area cannot be loaded the request fails —
                synthetic roads are never substituted for real ones.
              </p>
            </div>
          )}

          {/* Loaded-network provenance, exactly as the backend reported it. */}
          {networkMeta && (
            <div className="grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5 font-mono text-[9px] text-gray-400 border-t border-[#332E29]/60 pt-1.5">
              <span className="text-gray-500">Network:</span>
              <span className={networkMeta.dataSource === 'openstreetmap' ? 'text-[#8FBAC9]' : 'text-gray-300'}>
                {networkMeta.dataSource === 'openstreetmap' ? 'OpenStreetMap' : 'Synthetic'}
                {networkMeta.geometrySource ? ` · ${networkMeta.geometrySource} geometry` : ''}
              </span>

              {networkMeta.location?.display_name && (
                <>
                  <span className="text-gray-500">Place:</span>
                  <span className="truncate" title={networkMeta.location.display_name}>
                    {networkMeta.location.display_name}
                  </span>
                </>
              )}

              {networkMeta.provenance && (
                <>
                  <span className="text-gray-500">OSM data:</span>
                  <span>{networkMeta.provenance}{networkMeta.retrievedAt ? ` · ${networkMeta.retrievedAt}` : ''}</span>
                </>
              )}

              {networkMeta.osm?.junction_nodes != null && (
                <>
                  <span className="text-gray-500">Extract:</span>
                  <span>
                    {networkMeta.osm.junction_nodes} junctions · {networkMeta.osm.directed_edges} directed edges
                    {networkMeta.osm.oneway_forward != null ? ` · ${networkMeta.osm.oneway_forward + (networkMeta.osm.oneway_reverse || 0)} one-way` : ''}
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onGenerate?.()}
            disabled={loading}
            className="w-full py-1 text-gray-400 hover:text-gray-200 hover:bg-[#26221D]/50 rounded transition-colors text-[10px] focus-visible:ring-2 focus-visible:ring-[#C6602E]"
          >
            Generate New Scenario
          </button>
          <button
            onClick={onReplay}
            disabled={loading || !scenario}
            title="Re-run generate + optimize with the exact same seed and config"
            className="w-full py-1 text-gray-400 hover:text-gray-200 hover:bg-[#26221D]/50 rounded transition-colors text-[10px] focus-visible:ring-2 focus-visible:ring-[#C6602E] disabled:opacity-40 flex items-center justify-center gap-1"
          >
            <RotateCcw size={10} />
            Replay Run
          </button>
        </div>

        <button
          onClick={onOptimize}
          disabled={loading}
          className="w-full py-2.5 bg-[#C6602E] hover:bg-[#B0552A] text-white rounded-md text-sm font-bold flex items-center justify-center gap-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-[#C6602E] focus-visible:ring-offset-2 focus-visible:ring-offset-[#171513]"
        >
          <Zap size={16} />
          OPTIMIZE FLEET
        </button>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onSimulateIncident}
            disabled={!canSimulateIncident}
            title={!currentResult ? 'Optimize the fleet first to have an active route to disrupt' : ''}
            className="py-1.5 bg-[#3A1C18]/80 border border-[#5A2C26] text-[#E8918A] hover:bg-[#3A1C18] rounded flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-[11px] focus-visible:ring-2 focus-visible:ring-[#C1443B]"
          >
            <AlertTriangle size={12} className="flex-shrink-0" />
            Simulate Incident
          </button>

          <button
            onClick={onReOptimize}
            disabled={!canReOptimize}
            title={!incidentInfo ? 'Simulate a traffic incident first' : ''}
            className="py-1.5 bg-[#3A2E14]/80 border border-[#5A4A22] text-[#E8C578] hover:bg-[#3A2E14] rounded flex items-center justify-center gap-1.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed text-[11px] focus-visible:ring-2 focus-visible:ring-[#E8A93A]"
          >
            <RefreshCw size={12} className="flex-shrink-0" />
            Re-Optimize
          </button>
        </div>

        <button
          onClick={onRunBenchmark}
          disabled={loading}
          className="w-full py-1.5 bg-[#1E2A33]/60 border border-[#2E4A56] text-[#8FBAC9] hover:bg-[#1E2A33] rounded flex items-center justify-center gap-1.5 transition-colors disabled:opacity-50 text-[11px] focus-visible:ring-2 focus-visible:ring-[#5D7A9E]"
        >
          <BarChart2 size={12} />
          Run Benchmark
        </button>
      </div>

      {/* 1b. ENVIRONMENTAL CONDITIONS */}
      {/* Every value displayed here comes from the backend condition engine.
          Nothing is computed in React - the selects send a request, and the
          status lines below echo what the backend reported back. */}
      <div className="bg-[#141210]/50 border border-[#332E29] rounded-lg p-2.5 space-y-2">
        <div className="flex items-center gap-1.5 text-gray-300 font-semibold uppercase tracking-wider text-[10px]">
          <CloudRain size={12} className="text-[#5F8A80]" />
          Conditions
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <label htmlFor="traffic-mode" className="text-gray-400 block text-[10px]">
              Simulated Traffic
            </label>
            <select
              id="traffic-mode"
              value={trafficMode}
              disabled={loading || !scenarioId}
              onChange={(e) => onApplyConditions?.(e.target.value, weatherEnabled)}
              className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-1 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] text-[10px] disabled:opacity-40"
            >
              <option value="normal">Normal (1.0x)</option>
              <option value="moderate">Moderate (1.5x)</option>
              <option value="heavy">Heavy (2.5x)</option>
              <option value="severe">Severe (4.0x)</option>
            </select>
          </div>

          <div className="space-y-1">
            <span className="text-gray-400 block text-[10px]">Weather</span>
            <button
              onClick={() => onApplyConditions?.(trafficMode, !weatherEnabled)}
              disabled={loading || !scenarioId}
              aria-pressed={weatherEnabled}
              className={`w-full px-2 py-1 rounded border text-[10px] transition-colors disabled:opacity-40 focus-visible:ring-2 focus-visible:ring-[#5F8A80] ${
                weatherEnabled
                  ? 'bg-[#1E2A28] border-[#3A5A52] text-[#8FC9BA]'
                  : 'bg-[#26221D] border-[#3A342E] text-gray-400'
              }`}
            >
              {weatherEnabled ? 'Enabled' : 'Disabled'}
            </button>
          </div>
        </div>

        {/* Condition status - backend-reported provenance only. */}
        {conditionMeta && (
          <div className="grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5 font-mono text-[9px] text-gray-400 border-t border-[#332E29]/60 pt-1.5">
            <span className="text-gray-500">Traffic:</span>
            <span className="text-[#E8C578]">
              {conditionMeta.trafficSource === 'simulated' ? 'Simulated model' : conditionMeta.trafficSource}
              {conditionMeta.trafficMode ? ` · ${conditionMeta.trafficMode}` : ''}
            </span>

            <span className="text-gray-500">Weather:</span>
            <span className={conditionMeta.fallbackUsed ? 'text-[#E8918A]' : 'text-[#8FC9BA]'}>
              {conditionMeta.weatherSource
                ? `${conditionMeta.weatherSource}${conditionMeta.weatherCondition ? ` · ${conditionMeta.weatherCondition}` : ''}`
                : 'not applied'}
              {conditionMeta.conditions?.weather?.provider
                ? ` · ${conditionMeta.conditions.weather.provider}`
                : ''}
            </span>

            {/* Weather is the one genuinely observed input, so every field the
                provider returned is shown, and a field it did not return is
                simply absent rather than filled in. */}
            {conditionMeta.conditions?.weather?.description && (
              <>
                <span className="text-gray-500">Condition:</span>
                <span>
                  {conditionMeta.conditions.weather.description}
                  {conditionMeta.conditions.weather.temperature_c != null
                    ? ` · ${conditionMeta.conditions.weather.temperature_c}°C`
                    : ''}
                  {conditionMeta.conditions.weather.precipitation_mm != null
                    ? ` · ${conditionMeta.conditions.weather.precipitation_mm} mm`
                    : ''}
                  {conditionMeta.conditions.weather.wind_speed_kph != null
                    ? ` · ${conditionMeta.conditions.weather.wind_speed_kph} km/h`
                    : ''}
                  {` · ×${conditionMeta.conditions.weather.multiplier}`}
                </span>
              </>
            )}

            {conditionMeta.conditions?.weather?.observed_at && (
              <>
                <span className="text-gray-500">Observed at:</span>
                <span>{conditionMeta.conditions.weather.observed_at}</span>
              </>
            )}

            {conditionMeta.conditions?.weather?.retrieved_at && (
              <>
                <span className="text-gray-500">Retrieved:</span>
                <span>{conditionMeta.conditions.weather.retrieved_at}</span>
              </>
            )}

            {conditionMeta.conditions?.updated_at && (
              <>
                <span className="text-gray-500">Applied:</span>
                <span>{new Date(conditionMeta.conditions.updated_at).toLocaleTimeString()}</span>
              </>
            )}
          </div>
        )}

        {conditionMeta?.fallbackUsed && (
          <div className="text-[9px] text-[#E8918A] bg-[#3A1C18]/40 border border-[#5A2C26]/60 rounded px-2 py-1 leading-snug">
            Weather provider unavailable - fallback in use. No weather effect applied to edge costs.
          </div>
        )}

        <p className="text-[9px] text-gray-600 leading-snug">
          Traffic congestion is a documented simulation, not a live feed. Weather is a real
          Open-Meteo observation when the source above says network/cache.
        </p>

        {conditionsDirty && (
          <div className="text-[9px] text-[#E8C578] bg-[#3A2E14]/40 border border-[#5A4A22]/60 rounded px-2 py-1 leading-snug">
            Conditions changed - the routes shown were computed against the previous edge costs.
            Re-Optimize to update them.
          </div>
        )}
      </div>

      {/* 2. INCIDENT INFO PANEL */}
      {incidentInfo && (
        <div className="bg-[#3A1C18]/30 border border-[#5A2C26] rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2 text-[#E8918A] font-semibold uppercase tracking-wider mb-1">
            <AlertTriangle size={14} />
            ⚠ TRAFFIC INCIDENT
          </div>
          <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-gray-300 font-mono text-[10px]">
            <span className="text-gray-400">Road:</span>
            <span>{incidentInfo.roadName}</span>
            <span className="text-gray-400">Congestion:</span>
            <span className="text-[#E8A93A]">{incidentInfo.congestionFactor}×</span>
            <span className="text-gray-400">Affected:</span>
            <span>{incidentInfo.affectedVehicleIds?.map(id => `V0${id}`).join(', ') || 'None'}</span>
          </div>
          <div className="text-[10px] font-mono text-[#E8918A]/90 bg-[#3A1C18]/50 rounded px-2 py-1 inline-block">
            {incidentInfo.affectedVehicleIds?.length || 0} vehicles affected · {incidentInfo.affectedVehicleIds?.length || 0} routes impacted
          </div>
          {networkState === 'RE-OPTIMIZED' && (
            <div className="text-[10px] text-gray-400 font-mono border-t border-[#5A2C26]/60 pt-2 leading-relaxed">
              The affected route was reevaluated. Q-DFRO generated a new fleet solution.
            </div>
          )}
          <div className="border-t border-[#5A2C26]/60 pt-2">
            <RecoveryTimeline timeline={timeline} />
          </div>
        </div>
      )}

      {/* 2b. GENERIC WORKING INDICATOR - covers requests that don't have
          their own dedicated status block (generate, apply conditions,
          incident, benchmark). Optimize/Re-Optimize get their own richer
          block below, so this is suppressed for those two statuses to
          avoid showing two spinners at once. */}
      {loading && statusState !== 'OPTIMIZING' && statusState !== 'RE-OPTIMIZING' && (
        <div className="flex items-center gap-2 text-[10px] text-gray-400 font-mono bg-[#141210]/50 border border-[#332E29] rounded-lg px-2.5 py-1.5">
          <div className="w-3 h-3 border-2 border-[#C6602E] border-t-transparent rounded-full animate-spin flex-shrink-0"></div>
          Working...
        </div>
      )}

      {/* 3. OPTIMIZATION STATE */}
      {(statusState === 'OPTIMIZING' || statusState === 'RE-OPTIMIZING') && (
        <div className="bg-[#3A2318]/30 border border-[#5A3A22] rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2 text-[#C6602E] font-semibold uppercase tracking-wider">
            <Activity size={14} className="animate-pulse" />
            QPSO {statusState === 'RE-OPTIMIZING' ? 'RE-OPTIMIZING' : 'OPTIMIZING'}
          </div>
          <div className="text-gray-400 text-[10px]">
            Searching for a lower-cost feasible fleet solution...
          </div>
          <div className="flex justify-center py-2">
            <div className="w-4 h-4 border-2 border-[#C6602E] border-t-transparent rounded-full animate-spin"></div>
          </div>
        </div>
      )}

      {/* 4. ADVANCED SECTION */}
      <div className="pt-2 border-t border-[#332E29] mt-auto">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          aria-expanded={showAdvanced}
          className="flex items-center gap-1.5 text-gray-400 hover:text-gray-200 transition-colors py-1 w-full text-left focus-visible:ring-2 focus-visible:ring-[#C6602E] rounded"
        >
          {showAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <Settings size={12} className="ml-1" />
          Advanced Solver Settings
        </button>

        <div className={`advanced-collapse ${showAdvanced ? 'expanded' : ''}`}>
          <div className="mt-3 space-y-3 p-2 bg-[#141210]/50 rounded-lg border border-[#332E29]/50">
            <div className="space-y-1">
              <label htmlFor="solver-algorithm" className="text-gray-400 block text-[10px]">Active Solver</label>
              <select
                id="solver-algorithm"
                value={config.algorithm || 'qpso'}
                onChange={(e) => handleConfigChange('algorithm', e.target.value)}
                className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-1 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E]"
              >
                <option value="qpso">QPSO</option>
                <option value="pso">PSO</option>
                <option value="ga">GA</option>
                <option value="greedy">Greedy</option>
                <option value="exact">Exact (&le;10 jobs)</option>
              </select>
            </div>

            {config.algorithm === 'qpso' && (
              <label htmlFor="use-local-search" className="flex items-center gap-2 text-[11px] text-gray-300 cursor-pointer">
                <input
                  id="use-local-search"
                  type="checkbox"
                  checked={config.use_local_search !== false}
                  onChange={(e) => handleConfigChange('use_local_search', e.target.checked)}
                  className="accent-[#C6602E]"
                />
                2-opt/or-opt local search
                <span
                  title="Refines QPSO's best-found routes every few iterations by untangling crossings (2-opt) and relocating stops between vehicles (or-opt). On by default - without it, QPSO measurably loses to Greedy at 30+ jobs. Turn off to see the un-hybridized ablation baseline."
                  className="text-gray-500 hover:text-gray-300 cursor-help"
                >
                  <Info size={11} />
                </span>
              </label>
            )}

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <label htmlFor="solver-pop-size" className="text-gray-400 block text-[10px]">Pop Size</label>
                <input
                  id="solver-pop-size"
                  type="number"
                  value={config.population_size || 40}
                  onChange={(e) => handleConfigChange('population_size', Number(e.target.value))}
                  className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-1 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono"
                />
              </div>
              <div className="space-y-1">
                <label htmlFor="solver-max-iter" className="text-gray-400 block text-[10px]">Max Iter</label>
                <input
                  id="solver-max-iter"
                  type="number"
                  value={config.max_iterations || 100}
                  onChange={(e) => handleConfigChange('max_iterations', Number(e.target.value))}
                  className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-1 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono"
                />
              </div>
            </div>

            <div className="space-y-1">
              <label htmlFor="solver-seed" className="text-gray-400 block text-[10px]">Random Seed (0 = auto)</label>
              <input
                id="solver-seed"
                type="number"
                value={config.seed || 42}
                onChange={(e) => handleConfigChange('seed', Number(e.target.value))}
                className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-2 py-1 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono"
              />
            </div>

            <div className="pt-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-gray-400 block text-[10px]">Objective Weights</span>
                {previewCost != null && (
                  <span className="text-[10px] font-mono text-[#C6602E] tabular-nums">
                    Preview: {previewLoading ? '…' : previewCost.toFixed(2)}
                  </span>
                )}
              </div>
              {currentResult && (
                <p className="text-[9px] text-gray-600 mb-1.5 leading-snug">
                  Preview re-scores the current routes with these weights (backend-evaluated) - click Optimize to actually re-route.
                </p>
              )}
              <div className="grid grid-cols-2 gap-2">
                <div className="flex items-center gap-1">
                  <label htmlFor="weight-alpha" className="text-[10px] text-gray-500 w-4">α</label>
                  <input
                    id="weight-alpha"
                    type="number" step="0.1"
                    value={config.weights?.alpha || 1.0}
                    onChange={(e) => handleWeightChange('alpha', Number(e.target.value))}
                    className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-1.5 py-0.5 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono text-[10px]"
                  />
                </div>
                <div className="flex items-center gap-1">
                  <label htmlFor="weight-beta" className="text-[10px] text-gray-500 w-4">β</label>
                  <input
                    id="weight-beta"
                    type="number" step="0.1"
                    value={config.weights?.beta || 1.0}
                    onChange={(e) => handleWeightChange('beta', Number(e.target.value))}
                    className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-1.5 py-0.5 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono text-[10px]"
                  />
                </div>
                <div className="flex items-center gap-1">
                  <label htmlFor="weight-gamma" className="text-[10px] text-gray-500 w-4">γ</label>
                  <input
                    id="weight-gamma"
                    type="number" step="0.1"
                    value={config.weights?.gamma || 1.0}
                    onChange={(e) => handleWeightChange('gamma', Number(e.target.value))}
                    className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-1.5 py-0.5 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono text-[10px]"
                  />
                </div>
                <div className="flex items-center gap-1">
                  <label htmlFor="weight-penalty" className="text-[10px] text-gray-500 w-4">P</label>
                  <input
                    id="weight-penalty"
                    type="number" step="10"
                    value={config.weights?.penalty_weight || 1000}
                    onChange={(e) => handleWeightChange('penalty_weight', Number(e.target.value))}
                    className="w-full bg-[#26221D] border border-[#3A342E] text-gray-200 rounded px-1.5 py-0.5 outline-none focus:border-[#C6602E] focus-visible:ring-2 focus-visible:ring-[#C6602E] font-mono text-[10px]"
                  />
                </div>
              </div>
            </div>

            {/* Run manifest - read back from GET /api/scenario/{id}/manifest
                so it reports what the server actually holds for this run,
                rather than echoing this component's own state. A field the
                backend does not know (a synthetic network has no location)
                is shown as "—", never filled in. */}
            {manifest && (
              <div className="pt-2 border-t border-[#332E29]/60 space-y-1">
                <div className="flex items-center gap-1.5 text-gray-400 text-[10px] uppercase tracking-wider">
                  <FileText size={11} />
                  Run Manifest (server-reported)
                </div>
                <div className="grid grid-cols-[auto,1fr] gap-x-2 gap-y-0.5 font-mono text-[9px] text-gray-400">
                  <span className="text-gray-500">Run ID:</span>
                  <span className="truncate" title={manifest.scenario_hash}>{manifest.scenario_hash || '—'}</span>

                  <span className="text-gray-500">Location:</span>
                  <span className="truncate" title={manifest.location?.location?.display_name || ''}>
                    {manifest.location?.location?.display_name
                      || (manifest.data_source === 'openstreetmap' ? 'OpenStreetMap area' : '— (synthetic network)')}
                  </span>

                  <span className="text-gray-500">Seed:</span>
                  <span>{manifest.seed ?? '—'}</span>

                  <span className="text-gray-500">Algorithm:</span>
                  <span>{manifest.solver?.algorithm || '—'}</span>

                  <span className="text-gray-500">Population:</span>
                  <span>{manifest.solver?.population_size ?? '—'}</span>

                  <span className="text-gray-500">Iterations:</span>
                  <span>{manifest.solver?.max_iterations ?? '—'}</span>

                  <span className="text-gray-500">Traffic mode:</span>
                  <span>
                    {manifest.conditions?.traffic_mode || '—'}
                    {manifest.conditions?.traffic_is_simulated ? ' (simulated)' : ''}
                    {manifest.conditions?.traffic_formulation ? ` · ${manifest.conditions.traffic_formulation}` : ''}
                  </span>

                  <span className="text-gray-500">Weather src:</span>
                  <span>
                    {manifest.conditions?.weather_enabled
                      ? `${manifest.conditions.weather_source || 'unknown'} · ${manifest.conditions.weather_condition || 'unknown'} · ×${manifest.conditions.weather_multiplier}`
                      : 'disabled'}
                  </span>

                  <span className="text-gray-500">Incidents:</span>
                  <span>{manifest.conditions?.incident_edge_count ?? 0} edge(s)</span>

                  <span className="text-gray-500">Geometry:</span>
                  <span>{manifest.geometry_source || '—'}</span>

                  <span className="text-gray-500">Condition sig:</span>
                  <span className="truncate">{manifest.conditions?.signature || '— (none applied)'}</span>

                  <span className="text-gray-500">Network:</span>
                  <span>
                    {manifest.network?.node_count} nodes · {manifest.network?.edge_count} edges ·{' '}
                    {manifest.network?.job_count} jobs · {manifest.network?.vehicle_count} vehicles
                  </span>
                </div>
              </div>
            )}
          </div>
          </div>
      </div>
    </div>
  );
}
