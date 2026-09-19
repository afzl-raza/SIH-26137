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
  RotateCcw
} from 'lucide-react';
import RecoveryTimeline from './RecoveryTimeline';

export default function ControlPanel({
  scenario,
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
  timeline
}) {
  // Demo state-machine guards: an incident can't be simulated before there's
  // an optimized route to disrupt, and re-optimization is meaningless before
  // an incident has actually changed the scenario's traffic state.
  const canSimulateIncident = Boolean(currentResult) && !loading;
  const canReOptimize = Boolean(incidentInfo) && !loading;
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
    if (!currentResult?.routes?.length || !scenario) {
      setPreviewCost(null);
      return;
    }
    setPreviewLoading(true);
    const timer = setTimeout(() => {
      fetch('/api/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario,
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
  }, [config.weights, currentResult, scenario]);

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
            <span className={hasCongestion ? 'text-[#E8A93A]' : 'text-[#6B9A57]'}>
              Traffic: {hasCongestion ? 'Congested' : 'Normal'}
            </span>
            <span className="text-gray-600">·</span>
            <span className="text-[#C6602E] font-bold">{healthLabel}</span>
          </div>
        )}

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onGenerate}
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
          </div>
          </div>
      </div>
    </div>
  );
}
