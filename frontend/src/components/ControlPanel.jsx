import React, { useState, useEffect } from 'react';
import {
  Zap,
  AlertTriangle,
  RefreshCw,
  BarChart2,
  Settings,
  ChevronRight,
  ChevronDown,
  RotateCcw,
  CloudRain,
  MapPin,
  FileText
} from 'lucide-react';
import RecoveryTimeline from './RecoveryTimeline';
import VehicleLoader from './ui/VehicleLoader';
import Button from './ui/Button';
import SegmentedControl from './ui/SegmentedControl';
import ControlSection from './ui/ControlSection';
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
  const isOptimizing = statusState === 'OPTIMIZING' || statusState === 'RE-OPTIMIZING';

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
    <div className="clean-panel p-3.5 rounded-xl space-y-4 border border-[#332E29] text-xs shadow-xl w-full h-full flex flex-col">
      {scenario && (
        <div className="font-mono text-gray-300 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[11px]">
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

      {/* 01. SCENARIO */}
      <ControlSection index={1} title="Scenario" icon={MapPin}>
        <div className="bg-[#141210]/50 border border-[#332E29] rounded-lg p-2.5 space-y-2">
          <SegmentedControl
            options={[
              { id: 'synthetic', label: 'Synthetic' },
              { id: 'osm', label: 'OpenStreetMap' }
            ]}
            value={networkSource}
            onChange={(id) => setNetworkSource?.(id)}
            disabled={loading}
            className="!grid-cols-2"
          />

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
              <Button
                variant="secondary"
                onClick={() => onGenerate?.('osm')}
                disabled={loading || !place.trim()}
                disabledHint={!place.trim() ? 'Enter a location to load its road network.' : undefined}
              >
                Load Real Road Network
              </Button>
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
          <Button variant="tertiary" size="sm" onClick={() => onGenerate?.()} disabled={loading}>
            Generate New Scenario
          </Button>
          <Button
            variant="tertiary"
            size="sm"
            icon={RotateCcw}
            onClick={onReplay}
            disabled={loading || !scenario}
            title="Re-run generate + optimize with the exact same seed and config"
          >
            Replay Run
          </Button>
        </div>
      </ControlSection>

      {/* 02. CONDITIONS */}
      <ControlSection index={2} title="Conditions" icon={CloudRain}>
        <div className="bg-[#141210]/50 border border-[#332E29] rounded-lg p-2.5 space-y-2">
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
              <SegmentedControl
                options={[
                  { id: 'disabled', label: 'Disabled' },
                  { id: 'enabled', label: 'Enabled', activeClassName: 'bg-[#1E2A28] border-[#3A5A52] text-[#8FC9BA]' }
                ]}
                value={weatherEnabled ? 'enabled' : 'disabled'}
                onChange={(id) => onApplyConditions?.(trafficMode, id === 'enabled')}
                disabled={loading || !scenarioId}
                className="!grid-cols-2"
              />
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
      </ControlSection>

      {/* 03. OPERATIONS */}
      <ControlSection index={3} title="Operations" icon={Zap}>
        <Button variant="primary" size="lg" icon={Zap} onClick={onOptimize} disabled={loading}>
          Optimize Fleet
        </Button>

        <div className="grid grid-cols-2 gap-2">
          <Button
            variant="destructive"
            size="sm"
            icon={AlertTriangle}
            onClick={onSimulateIncident}
            disabled={!canSimulateIncident}
            disabledHint={!currentResult ? 'Optimize the fleet first to have an active route to disrupt.' : undefined}
          >
            Simulate Incident
          </Button>

          <Button
            variant="warning"
            size="sm"
            icon={RefreshCw}
            onClick={onReOptimize}
            disabled={!canReOptimize}
            disabledHint={!incidentInfo && !conditionsDirty ? 'Simulate an incident or change conditions first.' : undefined}
          >
            Re-Optimize
          </Button>
        </div>

        <Button variant="secondary" size="sm" icon={BarChart2} onClick={onRunBenchmark} disabled={loading}>
          Run Benchmark
        </Button>
      </ControlSection>

      {/* INCIDENT INFO PANEL */}
      {incidentInfo && (
        <div className="bg-[#3A1C18]/30 border border-[#5A2C26] rounded-lg p-3 space-y-2">
          <div className="flex items-center gap-2 text-[#E8918A] font-semibold uppercase tracking-wider mb-1">
            <AlertTriangle size={14} />
            Traffic Incident
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

      {/* GENERIC WORKING INDICATOR - covers requests that don't have their
          own dedicated status block (generate, apply conditions, incident,
          benchmark). Optimize/Re-Optimize get the richer VehicleLoader block
          below, so this is suppressed for those two statuses to avoid
          showing two loading indicators at once. */}
      {loading && !isOptimizing && (
        <div className="flex items-center gap-2 text-[10px] text-gray-400 font-mono bg-[#141210]/50 border border-[#332E29] rounded-lg px-2.5 py-1.5">
          <div className="w-3 h-3 border-2 border-[#C6602E] border-t-transparent rounded-full animate-spin flex-shrink-0" />
          Working...
        </div>
      )}

      {/* OPTIMIZATION STATE - branded vehicle loader, indeterminate (no
          real intermediate progress exists to report). */}
      {isOptimizing && (
        <div className="bg-[#3A2318]/30 border border-[#5A3A22] rounded-lg p-3">
          <VehicleLoader
            label={statusState === 'RE-OPTIMIZING' ? 'Re-Optimizing Routes' : 'Optimizing Routes'}
            sublabel="Searching for a lower-cost feasible fleet solution..."
          />
        </div>
      )}

      {/* 04. SOLVER (ADVANCED) */}
      <div className="pt-2 border-t border-[#332E29] mt-auto">
        <Button
          variant="tertiary"
          size="sm"
          fullWidth
          onClick={() => setShowAdvanced(!showAdvanced)}
          aria-expanded={showAdvanced}
          className="justify-start"
        >
          <span className="flex items-center gap-1.5">
            {showAdvanced ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            <Settings size={12} />
            04 · Solver Settings
          </span>
        </Button>

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
              </select>
            </div>

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
