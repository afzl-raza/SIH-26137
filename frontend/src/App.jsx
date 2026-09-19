import React, { useState, useEffect, useMemo } from 'react';
import NetworkMap from './components/NetworkMap';
import ControlPanel from './components/ControlPanel';
import VehicleInspector from './components/VehicleInspector';
import MetricCards from './components/MetricCards';
import BenchmarkPanel from './components/BenchmarkPanel';
import WorkflowIndicator from './components/WorkflowIndicator';
import QPSOExplainability from './components/QPSOExplainability';
import ArchitectureSnapshot from './components/ArchitectureSnapshot';
import ScalabilityPanel from './components/ScalabilityPanel';
import ReproducibilityPanel from './components/ReproducibilityPanel';
import Logo from './components/Logo';
import { apiFetch } from './api';
import { Activity } from 'lucide-react';

export default function App() {
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

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [statusState, setStatusState] = useState('INITIAL');
  const [networkState, setNetworkState] = useState('NORMAL');
  const [timeline, setTimeline] = useState(null);

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
  const handleGenerateScenario = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch('/api/problem/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          num_nodes: 30,
          num_jobs: 15,
          num_vehicles: 3,
          seed: config.seed
        })
      });
      if (!res.ok) throw new Error('Failed to generate network scenario');
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
      return data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
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
      if (!res.ok) throw new Error('Optimization failed');
      const data = await res.json();

      if (currentResult) {
        setPreviousResult(currentResult);
      }
      setCurrentResult(data);
      setStatusState('OPTIMIZED');
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

      if (!res.ok) throw new Error('Failed to update traffic incident');
      const data = await res.json();
      setScenario(data.scenario);
      setStatusState('INCIDENT');
      setNetworkState('DISRUPTED');
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
        body: JSON.stringify({ scenario_id: scenarioId, config })
      });
      if (!res.ok) throw new Error('Benchmark failed');
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
      <header className="clean-panel border-b border-[#332E29] px-6 py-2.5 flex items-center justify-between shadow-xl sticky top-0 z-50">
        <div className="flex items-center space-x-3">
          <div className="bg-[#1E1B18] border border-[#3A342E] p-2 rounded-lg shadow-md">
            <Logo size={22} />
          </div>
          <div>
            <div className="flex items-center space-x-2.5">
              <span className="font-display font-bold text-base tracking-wide text-gray-100">
                Q-DFRO <span className="font-medium text-gray-400">Engine</span>
              </span>
              <span className="text-[10px] bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-2 py-0.5 rounded font-mono font-semibold">
                QPSO ENGINE
              </span>
            </div>
            <p className="text-[11px] text-gray-400 tracking-tight font-mono">
              Quantum-Inspired Fleet Optimization Engine
            </p>
          </div>
        </div>

        {/* Network State + Engine Status */}
        <div className="flex items-center space-x-6">
          <div className="flex items-center space-x-2 font-mono text-xs">
            <span className={`px-2.5 py-1 rounded text-xs font-bold uppercase flex items-center gap-1.5 ${
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

          <div className="flex items-center space-x-2 border-l border-[#332E29] pl-6 text-xs font-mono">
            <Activity className="w-4 h-4 text-[#6B9A57]" />
            <div>
              <span className="text-gray-500 block text-[10px] uppercase">Engine</span>
              <span className="text-[#6B9A57] font-semibold text-[11px]">Solver Ready</span>
            </div>
          </div>
        </div>
      </header>

      {/* ═══ WORKFLOW INDICATOR ═══ */}
      <WorkflowIndicator currentStage={demoStage} narrativeText={narrativeText} />

      {/* ═══ ERROR ALERT ═══ */}
      {error && (
        <div className="bg-[#3A1C18]/90 border border-[#5A2C26] text-[#E8918A] px-6 py-2 text-xs font-mono flex items-center justify-between">
          <span>ERROR: {error}</span>
          <button onClick={() => setError(null)} className="text-[#E8918A] hover:text-white font-bold ml-4">✕</button>
        </div>
      )}

      {/* ═══ MAIN WORKSPACE (75% Map / 25% Operations) ═══ */}
      {/* items-stretch (grid's own default, set explicitly for clarity):
          the map's wrapper below uses h-full instead of a fixed h-[620px]
          so it stretches to match the operations column's actual height
          instead of leaving that column's leftover height as dead space
          beside a fixed-size map - this showed up as an 800px+ empty gap
          once the sidebar grew tall (vehicle selected + benchmark run).
          min-h-[620px] is a floor for the stacked single-column layout on
          narrow viewports, where each grid item sizes its own row and a
          plain h-full would otherwise resolve ambiguously against an
          auto-sized row. */}
      <main className="flex-1 p-4 grid grid-cols-1 lg:grid-cols-4 gap-4 max-w-[1920px] w-full mx-auto items-stretch">
        {/* HERO MAP */}
        <div className="lg:col-span-3 min-h-[620px] h-full w-full">
          <NetworkMap
            scenario={scenario}
            scenarioId={scenarioId}
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
          />
        </div>

        {/* OPERATIONS PANEL */}
        <div className="space-y-4 flex flex-col">
          <ControlPanel
            scenario={scenario}
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
