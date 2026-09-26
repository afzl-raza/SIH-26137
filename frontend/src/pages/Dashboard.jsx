import React, { useState, useEffect, useMemo } from 'react';
import NetworkMap from '../components/NetworkMap';
import ControlPanel from '../components/ControlPanel';
import VehicleInspector from '../components/VehicleInspector';
import MetricCards from '../components/MetricCards';
import BenchmarkPanel from '../components/BenchmarkPanel';
import ArchetypeBenchmarkPanel from '../components/ArchetypeBenchmarkPanel';
import WorkflowIndicator from '../components/WorkflowIndicator';
import QPSOExplainability from '../components/QPSOExplainability';
import ArchitectureSnapshot from '../components/ArchitectureSnapshot';
import ScalabilityPanel from '../components/ScalabilityPanel';
import ReproducibilityPanel from '../components/ReproducibilityPanel';
import SiouxFallsPanel from '../components/SiouxFallsPanel';
import Logo from '../components/Logo';
import Badge from '../components/ui/Badge';
import IconButton from '../components/ui/IconButton';
import { ToastProvider, useToast } from '../components/ui/Toast';
import OperationOverlay from '../components/ui/OperationOverlay';
import { apiFetch } from '../api';
import { Activity, ArrowLeft, X } from 'lucide-react';

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

export default function Dashboard({ onExitToOverview }) {
  return (
    <ToastProvider>
      <DashboardShell onExitToOverview={onExitToOverview} />
    </ToastProvider>
  );
}

// Both Optimize and Run Benchmark are reachable from the Engineering
// Control Room (its ControlPanel), so by the time a real user click fires
// this toast, #results-section already exists on the page - it's just
// below the fold. A no-op if it somehow doesn't (e.g. the one automatic
// bootstrap optimize).
function scrollToId(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function scrollToResults() {
  scrollToId('results-section');
}

function scrollToBenchmark() {
  scrollToId('benchmark-section');
}

function DashboardShell({ onExitToOverview }) {
  const toast = useToast();

  // ─── Core State ──────────────────────────────────
  const [scenario, setScenario] = useState(null);
  // The backend owns the scenario after generation; requests refer to it
  // by id instead of uploading the whole graph on every interaction.
  const [scenarioId, setScenarioId] = useState(null);
  const [currentResult, setCurrentResult] = useState(null);
  const [previousResult, setPreviousResult] = useState(null);
  const [benchmarkData, setBenchmarkData] = useState(null);
  // True once road conditions change after the last benchmark ran - that
  // benchmark's results were computed against edge costs that no longer
  // apply, so the Executive Overview must not present them as a current
  // before/after comparison. Engineering Control Room still shows them.
  const [benchmarkStale, setBenchmarkStale] = useState(false);
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
  // CVRPTW, opt-in. Sent to /api/problem/generate; off by default so a fresh
  // scenario behaves exactly as it always has.
  const [timeWindows, setTimeWindows] = useState(false);
  const [twWidthMin, setTwWidthMin] = useState(60);
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
  // When the currently-displayed result actually arrived, captured on this
  // client at that moment - not a backend timestamp, and not reused across
  // a later run until that run's own optimize call resolves.
  const [resultCompletedAt, setResultCompletedAt] = useState(null);

  const [loading, setLoading] = useState(false);
  // Which real request is in flight - drives the friendly OperationOverlay's
  // copy. Never used to fabricate progress, only to pick the right sentence
  // for a genuinely-running request.
  const [activeOperation, setActiveOperation] = useState(null);
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

  // ─── Auto-bootstrap on startup ───────────────────
  // Loads a real scenario, then runs exactly one real Optimize against it
  // using a fast solver preset - separate from `config` (which stays at
  // the slower, "watch it work" defaults Advanced Solver Settings shows
  // and manual runs use) - so the Executive Overview isn't empty on first
  // load, without a multi-second wait and without the multi-stage
  // auto-chain (incident/re-optimize/benchmark) that made everything feel
  // like it was "just happening." Those three stay entirely manual.
  const FAST_BOOTSTRAP_CONFIG = { ...config, population_size: 20, max_iterations: 30 };
  const [autoBootstrapStage, setAutoBootstrapStage] = useState('start');

  useEffect(() => {
    handleGenerateScenario().then(() => setAutoBootstrapStage('generated'));
  }, []);

  useEffect(() => {
    if (autoBootstrapStage === 'generated' && scenarioId) {
      handleOptimize(scenarioId, FAST_BOOTSTRAP_CONFIG).then(() => setAutoBootstrapStage('done'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoBootstrapStage, scenarioId]);

  // ─── Friendly failure feedback ───────────────────
  // The persistent error banner keeps the real message for anyone
  // debugging; this adds a plain-language toast alongside it rather than
  // exposing that raw message (which can be a network/server string) as
  // the primary feedback.
  useEffect(() => {
    if (error) {
      toast('Something went wrong', {
        tone: 'error',
        detail: "We couldn't complete the route calculation. Please try again."
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error]);

  // ─── API: Generate Scenario ──────────────────────
  // Accepts an optional explicit source so a control can switch network kind
  // and generate in one action without waiting for a state update to land.
  const handleGenerateScenario = async (sourceOverride) => {
    const source = (typeof sourceOverride === 'string') ? sourceOverride : networkSource;
    setLoading(true);
    setActiveOperation('generate');
    setError(null);
    try {
      const body = {
        source,
        num_nodes: scenarioParams.num_nodes,
        num_jobs: scenarioParams.num_jobs,
        num_vehicles: scenarioParams.num_vehicles,
        demand_min: scenarioParams.demand_min,
        demand_max: scenarioParams.demand_max,
        seed: config.seed,
        time_windows: timeWindows,
        tw_width_min: Number(twWidthMin) || 60
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
      setBenchmarkStale(false);
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
      setResultCompletedAt(null);

      if (source === 'osm') {
        toast('Road network loaded', {
          detail: `${data.node_count ?? '—'} junctions · ${data.edge_count ?? '—'} streets (OpenStreetMap). Next: Optimize Fleet.`
        });
      } else {
        toast('Scenario generated', {
          detail: `${data.scenario?.vehicles?.length ?? 0} vehicles · ${data.scenario?.jobs?.length ?? 0} jobs · ${data.scenario?.edges?.length ?? 0} road segments. Next: Optimize Fleet.`
        });
      }

      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
      setActiveOperation(null);
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
    setActiveOperation('generate');
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
      setBenchmarkStale(false);
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
      setResultCompletedAt(null);
      setPlacementMode(false);
      setDraftDepotId(null);
      setDraftStopIds([]);
      toast('Custom depot and stops applied', {
        detail: `${data.scenario?.jobs?.length ?? 0} stops placed. Next: Optimize Fleet.`
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setActiveOperation(null);
    }
  };

  // ─── API: Reproducibility manifest ──────────────
  // Reads back what the server holds for this run. The solver settings are
  // passed so the backend echoes exactly the configuration this client used -
  // it does not retain them otherwise, and inventing them would defeat the
  // point of a manifest.
  const refreshManifest = async (activeScenarioId, configOverride) => {
    const id = activeScenarioId || scenarioId;
    if (!id) return;
    const cfg = configOverride || config;
    const params = new URLSearchParams({
      algorithm: cfg.algorithm,
      population_size: String(cfg.population_size),
      max_iterations: String(cfg.max_iterations)
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
  // `configOverride` lets a caller run a one-off solver configuration (the
  // auto-bootstrap's fast preset) without touching the `config` state that
  // Advanced Solver Settings displays and that manual runs use.
  const handleOptimize = async (scenarioIdOverride, configOverride) => {
    const activeScenarioId = (typeof scenarioIdOverride === 'string')
      ? scenarioIdOverride
      : scenarioId;
    if (!activeScenarioId) return;
    const activeConfig = configOverride || config;
    setLoading(true);
    setError(null);
    const isReopt = networkState === 'DISRUPTED';
    setActiveOperation(isReopt ? 'reoptimize' : 'optimize');
    setStatusState(isReopt ? 'RE-OPTIMIZING' : 'OPTIMIZING');
    const reoptimizeClickedAt = isReopt ? Date.now() : null;

    try {
      const res = await apiFetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: activeScenarioId, config: activeConfig })
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
      setResultCompletedAt(Date.now());
      setStatusState('OPTIMIZED');
      // The routes on screen now match the current edge costs again.
      setConditionsDirty(false);
      // The manifest describes the run that just happened, so refresh it here
      // rather than on a timer - with the config this run actually used, not
      // necessarily whatever `config` state currently holds.
      refreshManifest(activeScenarioId, activeConfig);
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

      toast('Route plan ready', {
        detail: `${data.routes?.length ?? 0} routes · ${data.total_travel_time?.toFixed(1) ?? '—'} min travel time. Your ${isReopt ? 'updated' : 'optimized'} routes are ready to review.`,
        action: { label: 'View results', onClick: scrollToResults }
      });
    } catch (err) {
      setError(err.message);
      setStatusState('ERROR');
    } finally {
      setLoading(false);
      setActiveOperation(null);
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
    setActiveOperation('incident');
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
      if (benchmarkData) setBenchmarkStale(true);

      // Routes already on screen were computed against the old edge costs.
      if (currentResult) {
        setConditionsDirty(true);
        setNetworkState('DISRUPTED');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setActiveOperation(null);
    }
  };

  // ─── API: Apply a traffic disruption to a specific edge ─────────
  // Shared by the auto-pick "Simulate Incident" button and the interactive
  // click-to-select-a-road flow (Row 9) - same real /api/traffic/update
  // call either way, only how the edge/factor are chosen differs.
  const applyIncident = async (targetSource, targetDest, congestionFactor) => {
    if (!scenario) return;
    setLoading(true);
    setActiveOperation('incident');
    setError(null);

    // A factor of exactly 1.0 clears an incident (see realdata/conditions.py
    // apply_incidents) rather than creating one - this is a reopen, not a
    // new disruption, and must not be reported as one.
    const isReopen = congestionFactor === 1.0;

    try {
      const updates = [{
        source: targetSource,
        destination: targetDest,
        traffic_factor: congestionFactor
      }];

      // Needed by both the incident and the reopen path (and the toast
      // below), so it lives outside the branch.
      const matchingEdge = scenario.edges.find(
        e => (e.source === targetSource && e.destination === targetDest) ||
             (e.source === targetDest && e.destination === targetSource)
      );
      const roadName = matchingEdge?.road_name || `Road ${targetSource}-${targetDest}`;

      if (!isReopen) {
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

        setSelectedIncidentEdge({ source: targetSource, destination: targetDest });
        setIncidentInfo({
          roadName,
          congestionFactor,
          affectedVehicleIds: affectedVehicleIds.length > 0 ? affectedVehicleIds : [1]
        });
        setTimeline({ incidentAt: Date.now() });
      }

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

      if (isReopen) {
        // Reopening still changes edge costs, so a re-optimize stays
        // meaningful even once every road is clear again.
        setConditionsDirty(true);
        const anyIncidentRemains = data.scenario.edges.some(e => e.has_incident);
        if (!anyIncidentRemains) {
          setNetworkState('NORMAL');
          setStatusState(currentResult ? 'OPTIMIZED' : 'READY');
          setSelectedIncidentEdge(null);
          setIncidentInfo(null);
        }
      } else {
        setStatusState('INCIDENT');
        setNetworkState('DISRUPTED');
      }
      refreshManifest(scenarioId);
      if (benchmarkData) setBenchmarkStale(true);

      if (isReopen) {
        toast('Road reopened', {
          detail: `${roadName} is clear again. Re-Optimize to update the route plan.`
        });
      } else {
        toast('Road conditions updated', {
          tone: 'error',
          detail: `${roadName} is now congested (×${congestionFactor}). Re-Optimize to update the route plan.`
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setActiveOperation(null);
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
    setActiveOperation('benchmark');
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
      setBenchmarkStale(false);
      const algoCount = data.results ? Object.keys(data.results).length : 0;
      toast('Comparison ready', {
        detail: data.cached
          ? `Instant result - identical scenario and settings to an earlier run, so the ${algoCount} saved results were reused.`
          : `The route plans have been compared successfully - ${algoCount} options compared.`,
        action: { label: 'View benchmark details', onClick: scrollToBenchmark }
      });
      // Take the user straight to the results rather than leaving them
      // below the fold. Waits a frame so the panel has actually rendered.
      setTimeout(scrollToBenchmark, 150);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setActiveOperation(null);
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
      {/* Suppressed during the silent auto-bootstrap generate+optimize chain
          (see "Auto-bootstrap on startup" below) - that run populates the
          Executive Overview on first load and isn't a user-initiated
          operation, so it must not show the same full-screen overlay a real
          Optimize/Re-optimize/Benchmark click does. */}
      {loading && activeOperation && autoBootstrapStage === 'done' && <OperationOverlay operation={activeOperation} />}

      {/* ═══ HEADER ═══ */}
      {/* z-[1200]: must sit above Leaflet's internal panes/controls (400-1000),
          which otherwise scroll over the sticky header. Map containers are
          also `isolate`d, but this keeps the header safe regardless. */}
      <header className="clean-panel border-b border-[#332E29] px-3 sm:px-6 py-2 sm:py-2.5 flex flex-wrap lg:flex-nowrap items-center justify-between gap-x-3 gap-y-2 shadow-xl sticky top-0 z-[1200]">
        <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
          {onExitToOverview && (
            <button
              onClick={onExitToOverview}
              aria-label="Back to overview"
              title="Back to overview"
              className="hidden sm:flex items-center gap-1 text-[11px] font-mono text-gray-400 hover:text-[#E8A93A] border border-[#332E29] hover:border-[#5A3A22] rounded px-2 py-1.5 transition-colors"

            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Overview
            </button>
          )}
          <div className="bg-[#1E1B18] border border-[#3A342E] p-1.5 sm:p-2 rounded-lg shadow-md flex-shrink-0">
            <Logo size={20} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-display font-bold text-sm sm:text-base tracking-wide text-gray-100 whitespace-nowrap">
                Q-DFRO <span className="font-medium text-gray-400">Engine</span>
              </span>
              <Badge tone="accent" className="hidden sm:inline-flex">QPSO Engine</Badge>
            </div>
            <p className="hidden sm:block text-[11px] text-gray-400 tracking-tight font-mono">
              Quantum-Inspired Fleet Optimization Engine
            </p>
          </div>
        </div>

        {/* Network State + Engine Status */}
        <div className="flex items-center gap-3 sm:gap-6 justify-end">
          <div className="flex items-center space-x-2 font-mono text-xs">
            <Badge
              pulse={networkState === 'DISRUPTED' || statusState === 'RE-OPTIMIZING'}
              tone={
                networkState === 'DISRUPTED' || statusState === 'RE-OPTIMIZING'
                  ? 'red'
                  : networkState === 'RE-OPTIMIZED'
                  ? 'green'
                  : 'accent'
              }
              dotColor={
                networkState === 'DISRUPTED' || statusState === 'RE-OPTIMIZING' ? '#C1443B' :
                networkState === 'RE-OPTIMIZED' ? '#6B9A57' : '#C6602E'
              }
            >
              {networkStateLabel}
            </Badge>
          </div>

          <div className="hidden md:flex items-center space-x-2 border-l border-[#332E29] pl-3 sm:pl-6 text-xs font-mono">
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

      {/* ═══ MOBILE VIEWPORT SWITCHER (small screens) ═══ */}
      <div className="lg:hidden flex border-b border-[#332E29] bg-[#171513] p-1.5 gap-2 px-3 sm:px-6 shadow-md">
          <button
            onClick={() => setActiveMobileTab('map')}
            className={`flex-1 py-2 text-xs font-mono font-bold rounded transition-colors flex items-center justify-center gap-1.5 ${
              activeMobileTab === 'map'
                ? 'bg-[#C6602E] text-white shadow-sm'
                : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
            }`}
          >
            Network Map
          </button>
          <button
            onClick={() => setActiveMobileTab('controls')}
            className={`flex-1 py-2 text-xs font-mono font-bold rounded transition-colors flex items-center justify-center gap-1.5 ${
              activeMobileTab === 'controls'
                ? 'bg-[#C6602E] text-white shadow-sm'
                : 'bg-[#26221D] text-gray-400 hover:text-gray-200'
            }`}
          >
            Controls & Operations
          </button>
        </div>

      {/* ═══ ERROR ALERT ═══ */}
      {error && (
        <div className="bg-[#3A1C18]/90 border border-[#5A2C26] text-[#E8918A] px-4 sm:px-6 py-2 text-xs font-mono flex items-center justify-between">
          <span>ERROR: {error}</span>
          <IconButton icon={X} iconSize={12} onClick={() => setError(null)} aria-label="Dismiss error" className="ml-4 !text-[#E8918A] hover:!text-white" />
        </div>
      )}

      {/* ═══ ENGINEERING CONTROL ROOM (75% Map / 25% Operations) ═══ */}
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
            timeWindows={timeWindows}
            setTimeWindows={setTimeWindows}
            twWidthMin={twWidthMin}
            setTwWidthMin={setTwWidthMin}
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
      <footer id="results-section" className="p-4 pt-0 space-y-4 max-w-[1920px] w-full mx-auto scroll-mt-28">
        <MetricCards
          result={currentResult}
          previousResult={previousResult}
          weights={config.weights}
          manifest={manifest}
          completedAt={resultCompletedAt}
        />

        {benchmarkData && (
          // scroll-mt keeps the panel's title clear of the sticky header
          // when the post-benchmark auto-scroll lands on it.
          <div id="benchmark-section" className="scroll-mt-28">
            <BenchmarkPanel
              benchmarkData={benchmarkData}
              onClose={() => { setBenchmarkData(null); setPreviewedAlgorithm(null); }}
              config={config}
              onPreviewAlgorithm={setPreviewedAlgorithm}
              previewedAlgorithm={previewedAlgorithm}
            />
          </div>
        )}

        {demoStage === 'PROVE' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ScalabilityPanel />
            <ReproducibilityPanel />
          </div>
        )}

        <ArchetypeBenchmarkPanel config={config} />

        <SiouxFallsPanel />
      </footer>
    </div>
  );
}
