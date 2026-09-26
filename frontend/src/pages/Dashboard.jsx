import React, { useState, useEffect, useMemo } from 'react';
import NetworkMap from '../components/NetworkMap';
import ControlPanel from '../components/ControlPanel';
import VehicleInspector from '../components/VehicleInspector';
import MetricCards from '../components/MetricCards';
import BenchmarkPanel from '../components/BenchmarkPanel';
import WorkflowIndicator from '../components/WorkflowIndicator';
import QPSOExplainability from '../components/QPSOExplainability';
import ArchitectureSnapshot from '../components/ArchitectureSnapshot';
import ScalabilityPanel from '../components/ScalabilityPanel';
import ReproducibilityPanel from '../components/ReproducibilityPanel';
import Logo from '../components/Logo';
import { apiFetch } from '../api';
import { Activity, ArrowLeft } from 'lucide-react';

// Pulls the condition-provenance envelope out of any scenario-carrying
// response. Pure field selection - no value is derived or invented here; the
// backend is the only place edge costs and multipliers are computed.
function extractConditionMeta(data) {
  if (!data) return null;
  return {
    trafficSource: data.traffic_source ?? null,
    trafficMode: data.traffic_mode ?? null,
    weatherSource: data.weather_source ?? null,
    weatherCondition: data.weather_condition ?? null,
    fallbackUsed: Boolean(data.fallback_used),
    conditions: data.conditions ?? null
  };
}

export default function Dashboard({ onExitToLanding }) {
  // ─── Core State ──────────────────────────────────
  const [scenario, setScenario] = useState(null);
  // The backend owns the scenario after generation; requests refer to it
  // by id instead of uploading the whole graph on every interaction.
  const [scenarioId, setScenarioId] = useState(null);
  const [currentResult, setCurrentResult] = useState(null);
  const [previousResult, setPreviousResult] = useState(null);
  const [benchmarkData, setBenchmarkData] = useState(null);
  const [previewedAlgorithm, setPreviewedAlgorithm] = useState(null);
  const [selectedIncidentEdge, setSelectedIncidentEdge] = useState(null);
  const [incidentInfo, setIncidentInfo] = useState(null);

  const [selectedVehicle, setSelectedVehicle] = useState(null);
  const [selectedRoute, setSelectedRoute] = useState(null);

  // Environmental conditions currently baked into the scenario's edge costs.
  // Every field here is produced by the backend condition engine - nothing in
  // this component computes a multiplier, a travel time or a cost.
  const [conditionMeta, setConditionMeta] = useState(null);
  // The requested condition state. Separate from conditionMeta because the
  // select/toggle change immediately while the backend call is in flight.
  const [trafficMode, setTrafficMode] = useState('normal');
  const [weatherEnabled, setWeatherEnabled] = useState(false);
  // Set when conditions change after an optimization, so the UI can offer
  // Re-Optimize for the same reason it does after an incident: the routes on
  // screen were computed against edge costs that no longer apply.
  const [conditionsDirty, setConditionsDirty] = useState(false);

  // Where the network comes from. 'synthetic' keeps the generated graph the
  // demo has always started with; 'osm' runs the real chain the backend
  // already implements - Nominatim resolves the place, Overpass returns the
  // actual road network for it. The backend exposed this from Phase 3; until
  // now nothing in the UI could reach it.
  const [networkSource, setNetworkSource] = useState('synthetic');
  const [place, setPlace] = useState('');
  const [radiusM, setRadiusM] = useState(1200);
  // Synthetic-only scenario shape - previously hardcoded to 30/15/3 with no
  // way to change it from the UI even though the backend always supported
  // arbitrary values here.
  const [scenarioParams, setScenarioParams] = useState({
    num_nodes: 30,
    num_jobs: 15,
    num_vehicles: 3,
    demand_min: 5.0,
    demand_max: 15.0
  });

  // Manual depot/stop placement - lets the operator click existing map
  // nodes instead of accepting the generator's random placement. Draft
  // state only; nothing is sent to the backend until confirmed.
  const [placementMode, setPlacementMode] = useState(false);
  const [draftDepotId, setDraftDepotId] = useState(null);
  const [draftStopIds, setDraftStopIds] = useState([]);
  // Provenance of the loaded network, straight from the generate response.
  const [networkMeta, setNetworkMeta] = useState(null);
  // Reproducibility manifest for the current run, read back from the server
  // rather than assembled here, so it states what the backend actually holds.
  const [manifest, setManifest] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusState, setStatusState] = useState('INITIAL');
  const [networkState, setNetworkState] = useState('NORMAL');
  const [timeline, setTimeline] = useState(null);
  const [activeMobileTab, setActiveMobileTab] = useState('map'); // 'map' | 'controls' for mobile viewports

  const [config, setConfig] = useState({
    algorithm: 'qpso',
    population_size: 40,
    max_iterations: 100,
    seed: 42,
    weights: {
      alpha: 1.0,
      beta: 0.5,
      gamma: 1.0,
      penalty_weight: 1000.0
    }
  });

  // Preview a benchmark algorithm's routes on the map without disturbing
  // the actual applied optimization (currentResult) - real data from the
  // same benchmarkData the panel already displays.
  const previewResult = previewedAlgorithm && benchmarkData?.results?.[previewedAlgorithm]
    ? benchmarkData.results[previewedAlgorithm]
    : null;

  // ─── Demo Stage (derived) ────────────────────────
  const demoStage = useMemo(() => {
    if (benchmarkData) return 'PROVE';
    if (networkState === 'RE-OPTIMIZED') return 'RE_OPTIMIZE';
    if (statusState === 'RE-OPTIMIZING') return 'RE_OPTIMIZE';
    if (networkState === 'DISRUPTED' || statusState === 'INCIDENT') return 'DISRUPT';
    if (currentResult || statusState === 'OPTIMIZING' || statusState === 'OPTIMIZED') return 'PLAN';
    if (statusState === 'READY') return 'PLAN';
    return 'INITIAL';
  }, [statusState, networkState, currentResult, benchmarkData]);

  // ─── Dynamic Narrative ───────────────────────────
  const narrativeText = useMemo(() => {
    switch (statusState) {
      case 'INITIAL':
        return 'Generate a transportation network to begin optimization.';
      case 'READY':
        return 'Network loaded. Optimize fleet routes for current conditions.';
      case 'OPTIMIZING':
        return 'QPSO searching for optimal fleet route assignment...';
      case 'OPTIMIZED':
        if (networkState === 'RE-OPTIMIZED')
          return 'Fleet successfully re-routed around the disruption.';
        return 'Fleet routes optimized for current network conditions.';
      case 'INCIDENT':
        return 'Traffic disruption detected on an active fleet route.';
      case 'RE-OPTIMIZING':
        return 'QPSO searching for a lower-cost feasible fleet assignment...';
      default:
        return '';
    }
  }, [statusState, networkState]);

  // ─── Network State Label ─────────────────────────
  const networkStateLabel = useMemo(() => {
    if (statusState === 'RE-OPTIMIZING') return 'RE-OPTIMIZING';
    switch (networkState) {
      case 'DISRUPTED': return 'TRAFFIC DISRUPTION';
      case 'RE-OPTIMIZED': return 'NETWORK RE-OPTIMIZED';
      default: return 'NETWORK OPERATIONAL';
    }
  }, [networkState, statusState]);

  // ─── Auto-generate on startup ────────────────────
  useEffect(() => {
    handleGenerateScenario();
  }, []);

  // ─── API: Generate Scenario ──────────────────────
  // Accepts an optional explicit source so a control can switch network kind
  // and generate in one action without waiting for a state update to land.
  const handleGenerateScenario = async (sourceOverride) => {
    const source = (typeof sourceOverride === 'string') ? sourceOverride : networkSource;
    setLoading(true);
    setError(null);
    try {
      const body = {
        source,
        num_nodes: scenarioParams.num_nodes,
        num_jobs: scenarioParams.num_jobs,
        num_vehicles: scenarioParams.num_vehicles,
        demand_min: scenarioParams.demand_min,
        demand_max: scenarioParams.demand_max,
        seed: config.seed
      };
      // For an OSM run the location is the input: the backend geocodes it
      // through Nominatim and pulls the real road network for the result.
      if (source === 'osm') {
        body.place = place.trim();
        body.radius_m = Number(radiusM) || 1200;
      }

      const res = await apiFetch('/api/problem/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        // A cold OpenStreetMap fetch (uncached place/radius) legitimately
        // takes 20-90s+: Nominatim geocoding plus an Overpass query, with
        // retries across mirrors on the backend. The default apiFetch
        // timeout (15s) aborts this before the backend can finish, so this
        // call needs its own longer allowance. Synthetic generation stays
        // fast regardless, so the longer timeout costs it nothing.
        timeoutMs: 120000
      });
      if (!res.ok) {
        // The backend refuses rather than substituting synthetic roads when
        // a place cannot be resolved or Overpass is unreachable, so its
        // message is worth surfacing verbatim.
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to generate network scenario');
      }
      const data = await res.json();
      setScenario(data.scenario);
      setScenarioId(data.scenario_id);
      setCurrentResult(null);
      setPreviousResult(null);
      setBenchmarkData(null);
      setPreviewedAlgorithm(null);
      setSelectedIncidentEdge(null);
      setIncidentInfo(null);
      setSelectedVehicle(null);
      setSelectedRoute(null);
      setStatusState('READY');
      setNetworkState('NORMAL');
      setTimeline(null);
      setConditionMeta(extractConditionMeta(data));
      setConditionsDirty(false);
      // Pure field selection from the generate response - the backend states
      // its own provenance, nothing is inferred here.
      setNetworkMeta({
        dataSource: data.data_source ?? null,
        geometrySource: data.geometry_source ?? null,
        provenance: data.provenance ?? null,
        retrievedAt: data.retrieved_at ?? null,
        location: data.location ?? null,
        bbox: data.bbox ?? null,
        osm: data.osm ?? null,
        osmEndpoint: data.osm_endpoint ?? null,
        nodeCount: data.node_count ?? null,
        edgeCount: data.edge_count ?? null
      });
      setManifest(null);
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  };

  // ─── Manual depot/stop placement ─────────────────
  const handleTogglePlacementMode = () => {
    setPlacementMode(prev => {
      const next = !prev;
      if (next) {
        setDraftDepotId(null);
        setDraftStopIds([]);
      }
      return next;
    });
  };

  const handleClearPlacement = () => {
    setDraftDepotId(null);
    setDraftStopIds([]);
  };

  // First click sets the depot; clicking the depot again clears it so it can
  // be re-picked; every other click toggles that node as a delivery stop.
  const handlePlaceNode = (nodeId) => {
    if (draftDepotId === null) {
      setDraftDepotId(nodeId);
      return;
    }
    if (nodeId === draftDepotId) {
      setDraftDepotId(null);
      return;
    }
    setDraftStopIds(prev =>
      prev.includes(nodeId) ? prev.filter(id => id !== nodeId) : [...prev, nodeId]
    );
  };

  const handleConfirmPlacement = async () => {
    if (draftDepotId === null || draftStopIds.length === 0 || !scenarioId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/problem/customize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: scenarioId,
          depot_node_id: draftDepotId,
          job_node_ids: draftStopIds,
          demand_min: scenarioParams.demand_min,
          demand_max: scenarioParams.demand_max
        })
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to apply manual placement');
      }
      const data = await res.json();
      setScenario(data.scenario);
      setScenarioId(data.scenario_id);
      setCurrentResult(null);
      setPreviousResult(null);
      setBenchmarkData(null);
      setPreviewedAlgorithm(null);
      setSelectedIncidentEdge(null);
      setIncidentInfo(null);
      setSelectedVehicle(null);
      setSelectedRoute(null);
      setStatusState('READY');
      setNetworkState('NORMAL');
      setTimeline(null);
      setConditionMeta(extractConditionMeta(data));
      setConditionsDirty(false);
      setManifest(null);
      setPlacementMode(false);
      setDraftDepotId(null);
      setDraftStopIds([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── API: Reproducibility manifest ──────────────
  // Reads back what the server holds for this run. The solver settings are
  // passed so the backend echoes exactly the configuration this client used -
  // it does not retain them otherwise, and inventing them would defeat the
  // point of a manifest.
  const refreshManifest = async (activeScenarioId) => {
    const id = activeScenarioId || scenarioId;
    if (!id) return;
    const params = new URLSearchParams({
      algorithm: config.algorithm,
      population_size: String(config.population_size),
      max_iterations: String(config.max_iterations)
    });
    try {
      const res = await apiFetch(`/api/scenario/${id}/manifest?${params}`);
      if (res.ok) setManifest(await res.json());
    } catch {
      // A missing manifest is a display gap, never a reason to fail a run.
    }
  };

  // ─── API: Optimize ──────────────────────────────
  // Accepts an optional freshly-generated scenario to optimize immediately
  // (used by Replay Run) - otherwise falls back to the scenario already in
  // state. Guarded with a shape check rather than relying on the argument
  // being undefined, since this function is also used directly as a button
  // onClick handler, which would otherwise pass the DOM click event here.
  const handleOptimize = async (scenarioIdOverride) => {
    const activeScenarioId = (typeof scenarioIdOverride === 'string')
      ? scenarioIdOverride
      : scenarioId;
    if (!activeScenarioId) return;
    setLoading(true);
    setError(null);
    const isReopt = networkState === 'DISRUPTED';
    setStatusState(isReopt ? 'RE-OPTIMIZING' : 'OPTIMIZING');
    const reoptimizeClickedAt = isReopt ? Date.now() : null;

    try {
      const res = await apiFetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: activeScenarioId, config })
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Optimization failed');
      }
      const data = await res.json();

      if (currentResult) {
        setPreviousResult(currentResult);
      }
      setCurrentResult(data);
      setStatusState('OPTIMIZED');
      // The routes on screen now match the current edge costs again.
      setConditionsDirty(false);
      // The manifest describes the run that just happened, so refresh it here
      // rather than on a timer.
      refreshManifest(activeScenarioId);
      if (isReopt) {
        setNetworkState('RE-OPTIMIZED');
        // Recovery Timeline: the "Optimizing" duration is the backend's own
        // reported runtime_ms, not a client stopwatch guess (see Task.md /
        // Engineering.md - only the human-response segment is client-timed).
        setTimeline(prev => ({
          ...prev,
          reoptimizeClickedAt,
          completedAt: Date.now(),
          optimizingDurationMs: data.runtime_ms
        }));
      }
    } catch (err) {
      setError(err.message);
      setStatusState('ERROR');
    } finally {
      setLoading(false);
    }
  };

  // ─── API: Apply environmental conditions ────────────────────────
  // Sends the requested traffic level / weather toggle to the backend, which
  // recomputes every edge cost through the one condition engine and hands the
  // updated scenario back. This deliberately does NOT re-optimize: the user
  // clicks Re-Optimize, so "conditions changed -> routes changed" stays
  // visible as two separate steps.
  const handleApplyConditions = async (nextMode, nextWeather) => {
    if (!scenarioId) return;
    const mode = nextMode ?? trafficMode;
    const weather = nextWeather ?? weatherEnabled;

    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/scenario/conditions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario_id: scenarioId,
          traffic_mode: mode,
          weather_enabled: weather
        })
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to apply conditions');
      }
      const data = await res.json();
      setScenario(data.scenario);
      setConditionMeta(extractConditionMeta(data));
      setTrafficMode(mode);
      setWeatherEnabled(weather);
      refreshManifest(scenarioId);

      // Routes already on screen were computed against the old edge costs.
      if (currentResult) {
        setConditionsDirty(true);
        setNetworkState('DISRUPTED');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── API: Apply a traffic disruption to a specific edge ─────────
  // Shared by the auto-pick "Simulate Incident" button and the interactive
  // click-to-select-a-road flow (Row 9) - same real /api/traffic/update
  // call either way, only how the edge/factor are chosen differs.
  const applyIncident = async (targetSource, targetDest, congestionFactor) => {
    if (!scenario) return;
    setLoading(true);
    setError(null);

    try {
      // Find which vehicles use this edge on the current active routes
      const affectedVehicleIds = currentResult?.routes
        ? currentResult.routes
            .filter(r => {
              for (let i = 0; i < r.node_path.length - 1; i++) {
                if (
                  (r.node_path[i] === targetSource && r.node_path[i + 1] === targetDest) ||
                  (r.node_path[i] === targetDest && r.node_path[i + 1] === targetSource)
                ) return true;
              }
              return false;
            })
            .map(r => r.vehicle_id)
        : [];

      const matchingEdge = scenario.edges.find(
        e => (e.source === targetSource && e.destination === targetDest) ||
             (e.source === targetDest && e.destination === targetSource)
      );
      const roadName = matchingEdge?.road_name || `Road ${targetSource}-${targetDest}`;

      const updates = [{
        source: targetSource,
        destination: targetDest,
        traffic_factor: congestionFactor
      }];

      setSelectedIncidentEdge({ source: targetSource, destination: targetDest });
      setIncidentInfo({
        roadName,
        congestionFactor,
        affectedVehicleIds: affectedVehicleIds.length > 0 ? affectedVehicleIds : [1]
      });
      setTimeline({ incidentAt: Date.now() });

      const res = await apiFetch('/api/traffic/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId, updates })
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Failed to update traffic incident');
      }
      const data = await res.json();
      setScenario(data.scenario);
      setConditionMeta(extractConditionMeta(data));
      setStatusState('INCIDENT');
      setNetworkState('DISRUPTED');
      refreshManifest(scenarioId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // ─── API: Simulate Incident (auto-pick an edge on an active route) ───
  const handleSimulateIncident = async () => {
    if (!scenario || scenario.edges.length === 0) return;

    let targetSource = scenario.edges[0].source;
    let targetDest = scenario.edges[0].destination;

    // Prefer to disrupt an edge on the first vehicle's active route
    if (currentResult && currentResult.routes.length > 0) {
      const firstRoute = currentResult.routes[0];
      if (firstRoute.node_path.length >= 3) {
        targetSource = firstRoute.node_path[1];
        targetDest = firstRoute.node_path[2];
      }
    }

    await applyIncident(targetSource, targetDest, 3.5);
  };

  // ─── API: Disrupt a specific, user-chosen edge (Row 9) ──────────
  const handleDisruptEdge = async (source, destination, congestionFactor) => {
    await applyIncident(source, destination, congestionFactor);
  };

  // ─── API: Re-Optimize ──────────────────────────
  const handleReOptimize = async () => {
    await handleOptimize();
  };

  // ─── Replay Run ─────────────────────────────────
  // Re-issues the real generate + optimize API calls with the exact same
  // seed/config already in state. Deterministic by construction (tested
  // server-side in test_e6_reproducibility_determinism_and_stats) - this
  // doesn't simulate anything, it just runs the same real requests again.
  const handleReplay = async () => {
    const fresh = await handleGenerateScenario();
    if (fresh?.scenario_id) {
      await handleOptimize(fresh.scenario_id);
    }
  };

  // ─── API: Benchmark ─────────────────────────────
  const handleRunBenchmark = async () => {
    if (!scenario) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/benchmark', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId, config }),
        // Runs 3 population-based optimizers sequentially (pop_size *
        // max_iterations candidate evaluations each) against the full
        // scenario. On a large real OpenStreetMap extract this can take
        // well over the default 15s timeout even after fixing the
        // per-candidate edge-map rebuild (see fitness.build_edge_map).
        timeoutMs: 120000
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => null);
        throw new Error(detail?.detail || 'Benchmark failed');
      }
      const data = await res.json();
      setBenchmarkData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectVehicle = (vehicleObj, routeObj) => {
    setSelectedVehicle(vehicleObj);
    setSelectedRoute(routeObj);
  };

  // ═══════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════
  return (
    <div className="min-h-screen bg-[#0D0C0B] text-gray-100 flex flex-col font-sans selection:bg-[#C6602E] selection:text-white">

      {/* ═══ HEADER ═══ */}
      <header className="clean-panel border-b border-[#332E29] px-3 sm:px-6 py-2.5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 shadow-xl sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          {onExitToLanding && (
            <button
              onClick={onExitToLanding}
              aria-label="Back to landing page"
              className="hidden sm:flex items-center gap-1 text-[11px] font-mono text-gray-400 hover:text-[#E8A93A] border border-[#332E29] hover:border-[#5A3A22] rounded px-2 py-1.5 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Landing
            </button>
          )}
          <div className="bg-[#1E1B18] border border-[#3A342E] p-1.5 sm:p-2 rounded-lg shadow-md">
            <Logo size={20} />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-display font-bold text-sm sm:text-base tracking-wide text-gray-100">
                Q-DFRO <span className="font-medium text-gray-400">Engine</span>
              </span>
              <span className="text-[9px] sm:text-[10px] bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-1.5 py-0.5 rounded font-mono font-semibold">
                QPSO ENGINE
              </span>
            </div>
            <p className="text-[10px] sm:text-[11px] text-gray-400 tracking-tight font-mono">
              Quantum-Inspired Fleet Optimization Engine
            </p>
          </div>
        </div>

        {/* Network State + Engine Status */}
        <div className="flex items-center space-x-3 sm:space-x-6 w-full sm:w-auto justify-between sm:justify-end">
          <div className="flex items-center space-x-2 font-mono text-xs">
            <span className={`px-2 sm:px-2.5 py-1 rounded text-[10px] sm:text-xs font-bold uppercase flex items-center gap-1.5 ${
              networkState === 'DISRUPTED' || statusState === 'RE-OPTIMIZING'
                ? 'bg-[#3A1C18] text-[#E8918A] border border-[#5A2C26] animate-pulse'
                : networkState === 'RE-OPTIMIZED'
                ? 'bg-[#22301B] text-[#9FC589] border border-[#3A4A2E]'
                : 'bg-[#3A2318] text-[#E8A578] border border-[#5A3A22]'
            }`}>
              <span className={`w-2 h-2 rounded-full ${
                networkState === 'DISRUPTED' || statusState === 'RE-OPTIMIZING' ? 'bg-[#C1443B]' :
                networkState === 'RE-OPTIMIZED' ? 'bg-[#6B9A57]' : 'bg-[#C6602E]'
              }`}></span>
              {networkStateLabel}
            </span>
          </div>

          <div className="flex items-center space-x-2 border-l border-[#332E29] pl-3 sm:pl-6 text-xs font-mono">
            <Activity className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-[#6B9A57]" />
            <div>
              <span className="text-gray-500 block text-[9px] sm:text-[10px] uppercase">Engine</span>
              <span className="text-[#6B9A57] font-semibold text-[10px] sm:text-[11px]">Solver Ready</span>
            </div>
          </div>
        </div>
      </header>

      {/* ═══ WORKFLOW INDICATOR ═══ */}
      <WorkflowIndicator currentStage={demoStage} narrativeText={narrativeText} />

      {/* ═══ MOBILE VIEWPORT SWITCHER (VISIBLE ON SMALL SCREENS ONLY) ═══ */}
      <div className="lg:hidden flex border-b border-[#332E29] bg-[#171513] p-1.5 gap-2 px-3 sm:px-6 shadow-md sticky top-[57px] z-40">
        <button
          onClick={() => setActiveMobileTab('map')}
          className={`flex-1 py-2 text-xs font-mono font-bold rounded transition-colors flex items-center justify-center gap-1.5 ${
            activeMobileTab === 'map'
              ? 'bg-[#C6602E] text-white shadow-sm'
              : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
          }`}
        >
          <span>🗺️</span> Network Map
        </button>
        <button
          onClick={() => setActiveMobileTab('controls')}
          className={`flex-1 py-2 text-xs font-mono font-bold rounded transition-colors flex items-center justify-center gap-1.5 ${
            activeMobileTab === 'controls'
              ? 'bg-[#C6602E] text-white shadow-sm'
              : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
          }`}
        >
          <span>⚡</span> Controls & Operations
        </button>
      </div>

      {/* ═══ ERROR ALERT ═══ */}
      {error && (
        <div className="bg-[#3A1C18]/90 border border-[#5A2C26] text-[#E8918A] px-4 sm:px-6 py-2 text-xs font-mono flex items-center justify-between">
          <span>ERROR: {error}</span>
          <button onClick={() => setError(null)} className="text-[#E8918A] hover:text-white font-bold ml-4">✕</button>
        </div>
      )}

      {/* ═══ MAIN WORKSPACE (75% Map / 25% Operations) ═══ */}
      <main className="flex-1 p-2 sm:p-4 grid grid-cols-1 lg:grid-cols-4 gap-4 max-w-[1920px] w-full mx-auto items-stretch">
        {/* HERO MAP */}
        <div className={`lg:col-span-3 min-h-[350px] sm:min-h-[480px] lg:min-h-[620px] h-full w-full ${
          activeMobileTab === 'map' ? 'block' : 'hidden lg:block'
        }`}>
          <NetworkMap
            scenario={scenario}
            scenarioId={scenarioId}
            loading={loading}
            currentResult={currentResult}
            previousResult={previousResult}
            selectedIncidentEdge={selectedIncidentEdge}
            selectedVehicleId={selectedVehicle?.id}
            onSelectVehicle={handleSelectVehicle}
            weights={config.weights}
            onDisruptEdge={handleDisruptEdge}
            disruptDisabled={loading || !currentResult}
            previewResult={previewResult}
            previewedAlgorithm={previewedAlgorithm}
            placementMode={placementMode}
            draftDepotId={draftDepotId}
            draftStopIds={draftStopIds}
            onPlaceNode={handlePlaceNode}
          />
        </div>

        {/* OPERATIONS PANEL
            display must stay `flex` in every branch here - `flex` and
            `block` both set the same CSS property, and Tailwind's utility
            order (not JSX source order) decides the winner when both are
            present. `hidden lg:block` used to collapse this panel to
            display:block on every desktop-width view (verified: `lg:block`
            is later in Tailwind's generated stylesheet than the base
            `flex`, so it always won once the `lg:` media query matched),
            silently dropping the flex-column stacking this panel's
            children (ControlPanel/VehicleInspector/QPSOExplainability/
            ArchitectureSnapshot) are laid out to expect. `lg:flex` keeps
            it a flex container at every width the panel is visible at. */}
        <div className={`space-y-4 flex flex-col ${
          activeMobileTab === 'controls' ? 'flex' : 'hidden lg:flex'
        }`}>
          <ControlPanel
            scenario={scenario}
            scenarioId={scenarioId}
            config={config}
            setConfig={setConfig}
            onGenerate={handleGenerateScenario}
            onOptimize={handleOptimize}
            onSimulateIncident={handleSimulateIncident}
            onReOptimize={handleReOptimize}
            onReplay={handleReplay}
            onRunBenchmark={handleRunBenchmark}
            loading={loading}
            statusState={statusState}
            networkState={networkState}
            incidentInfo={incidentInfo}
            currentResult={currentResult}
            timeline={timeline}
            conditionMeta={conditionMeta}
            trafficMode={trafficMode}
            weatherEnabled={weatherEnabled}
            conditionsDirty={conditionsDirty}
            onApplyConditions={handleApplyConditions}
            networkSource={networkSource}
            setNetworkSource={setNetworkSource}
            place={place}
            setPlace={setPlace}
            radiusM={radiusM}
            setRadiusM={setRadiusM}
            networkMeta={networkMeta}
            manifest={manifest}
            scenarioParams={scenarioParams}
            setScenarioParams={setScenarioParams}
            placementMode={placementMode}
            onTogglePlacementMode={handleTogglePlacementMode}
            draftDepotId={draftDepotId}
            draftStopIds={draftStopIds}
            onClearPlacement={handleClearPlacement}
            onConfirmPlacement={handleConfirmPlacement}
          />

          <VehicleInspector
            vehicle={selectedVehicle}
            route={selectedRoute}
            scenario={scenario}
            onDeselect={() => {
              setSelectedVehicle(null);
              setSelectedRoute(null);
            }}
          />

          <QPSOExplainability config={config} scenario={scenario} />

          <ArchitectureSnapshot />
        </div>
      </main>

      {/* ═══ METRICS & ANALYTICS ═══ */}
      <footer className="p-4 pt-0 space-y-4 max-w-[1920px] w-full mx-auto">
        <MetricCards result={currentResult} previousResult={previousResult} weights={config.weights} />

        {benchmarkData && (
          <BenchmarkPanel
            benchmarkData={benchmarkData}
            onClose={() => { setBenchmarkData(null); setPreviewedAlgorithm(null); }}
            config={config}
            onPreviewAlgorithm={setPreviewedAlgorithm}
            previewedAlgorithm={previewedAlgorithm}
          />
        )}

        {demoStage === 'PROVE' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ScalabilityPanel />
            <ReproducibilityPanel />
          </div>
        )}
      </footer>
    </div>
  );
}
