import React, { useState } from 'react';
import { X, Trophy, Award, BarChart2, CheckCircle2, XCircle, ShieldCheck, Table2, Gauge, Zap } from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

// Single source of truth for per-algorithm color across the chart, bar
// visualization, and table - previously three separate switch statements
// that had to be kept in sync by hand.
export const ALGORITHM_COLORS = {
  greedy: { hex: '#6B9A57', text: 'text-[#6B9A57]', bg: 'bg-[#6B9A57]' },
  pso: { hex: '#5D7A9E', text: 'text-[#5D7A9E]', bg: 'bg-[#5D7A9E]' },
  ga: { hex: '#8A8C4E', text: 'text-[#8A8C4E]', bg: 'bg-[#8A8C4E]' },
  // Plain QPSO (no local search) - kept as an explicit ablation/comparison
  // entry, not the flagship result. qpso_ls (with the 2-opt/or-opt hybrid)
  // is the default algorithm and gets the brand accent instead.
  qpso: { hex: '#8C5A6E', text: 'text-[#8C5A6E]', bg: 'bg-[#8C5A6E]' },
  qpso_ls: { hex: '#C6602E', text: 'text-[#C6602E]', bg: 'bg-[#C6602E]' },
  exact: { hex: '#E8A93A', text: 'text-[#E8A93A]', bg: 'bg-[#E8A93A]' }
};
const DEFAULT_ALGORITHM_COLOR = { hex: '#9CA3AF', text: 'text-gray-500', bg: 'bg-gray-500' };

function getAlgorithmColor(id) {
  return ALGORITHM_COLORS[id] || DEFAULT_ALGORITHM_COLOR;
}

// Log scaling makes a bar chart readable when one algorithm's real measured
// value is orders of magnitude larger than the rest (e.g. an infeasible run
// at large scenario sizes can measure a cost or runtime 50-100x its peers -
// see experiments/E3_scalability). `+1` keeps a genuine 0 at 0 width instead
// of -Infinity, without distorting any non-zero value meaningfully.
function barWidthPct(value, max, useLog) {
  if (!(max > 0)) return 0;
  if (!useLog) return Math.min(100, (value / max) * 100);
  const logMax = Math.log10(max + 1);
  if (!(logMax > 0)) return 0;
  return Math.min(100, (Math.log10(value + 1) / logMax) * 100);
}

export default function BenchmarkPanel({ benchmarkData, onClose, config, onPreviewAlgorithm, previewedAlgorithm }) {
  const [barScale, setBarScale] = useState('linear'); // 'linear' | 'log'
  const [resultsView, setResultsView] = useState('bars'); // 'bars' | 'table'

  if (!benchmarkData || !benchmarkData.results) return null;

  const { results } = benchmarkData;
  // "exact" is only present when the scenario is small enough to solve
  // exactly (<=10 jobs) - absent otherwise, which resultsArray's filter
  // below handles the same way it already handles any other missing key.
  const algos = ['greedy', 'pso', 'ga', 'qpso', 'qpso_ls', 'exact'];

  const resultsArray = algos.map(k => ({ id: k, ...results[k] })).filter(r => r.total_cost !== undefined);

  if (resultsArray.length === 0) return null;

  const minCost = Math.min(...resultsArray.map(r => r.total_cost));
  const maxCost = Math.max(...resultsArray.map(r => r.total_cost));
  const maxRuntime = Math.max(...resultsArray.map(r => r.runtime_ms || 0));
  const bestAlgo = resultsArray.find(r => r.total_cost === minCost);
  // qpso_ls (QPSO + local search) is the default/flagship algorithm now -
  // this is what the summary line compares the winner against.
  const qpsoResult = results.qpso_ls;

  // Neutral, symmetric summary: whichever algorithm is empirically cheapest
  // gets the same treatment regardless of which one it is - QPSO is a
  // hypothesis under test, not a predetermined winner (Engineering.md Sec.1).
  let qpsoSummary = null;
  if (bestAlgo) {
    const bestLabel = bestAlgo.algorithm || bestAlgo.id.toUpperCase();
    const isQpsoBest = bestAlgo.id === 'qpso_ls';
    qpsoSummary = (
      <div className="bg-[#1E1B18] border border-[#3A342E] rounded-lg p-3 flex items-center gap-3">
        <Award className="text-gray-400 w-5 h-5 flex-shrink-0" />
        <span className="text-gray-300 text-sm">
          Lowest measured cost on this scenario: <span className="font-semibold text-white">{bestLabel}</span> at {minCost.toFixed(2)}
          {!isQpsoBest && qpsoResult?.total_cost !== undefined && (
            <span className="text-gray-500"> · QPSO+LS: {qpsoResult.total_cost.toFixed(2)} (+{((qpsoResult.total_cost - minCost) / minCost * 100).toFixed(1)}%)</span>
          )}
        </span>
      </div>
    );
  }

  // Convergence Chart data - "exact" is excluded on purpose: it solves
  // directly rather than iterating, so a convergence curve doesn't apply
  // to it (a single flat point would misrepresent what it does).
  const chartDatasets = [];
  ['pso', 'ga', 'qpso', 'qpso_ls'].forEach(id => {
    if (results[id] && results[id].convergence_history) {
      chartDatasets.push({
        label: results[id].algorithm || id.toUpperCase(),
        data: results[id].convergence_history,
        borderColor: getAlgorithmColor(id).hex,
        backgroundColor: getAlgorithmColor(id).hex,
        tension: 0.1,
        pointRadius: 0,
        borderWidth: 2
      });
    }
  });

  const chartData = {
    labels: chartDatasets.length > 0 ? Array.from({ length: chartDatasets[0].data.length }, (_, i) => i) : [],
    datasets: chartDatasets
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    // convergence_history is 100% real and already fully computed by the
    // time this renders - this is a short chart-draw-in flourish (Chart.js's
    // own animation), not a replay paced to resemble ongoing computation.
    animation: {
      duration: 400,
      easing: 'easeOutQuad'
    },
    scales: {
      x: {
        grid: { color: '#332E29' },
        ticks: { color: '#9CA3AF', maxTicksLimit: 10 }
      },
      y: {
        title: { display: true, text: 'Objective Cost', color: '#9CA3AF' },
        grid: { color: '#332E29' },
        ticks: { color: '#9CA3AF' }
      }
    },
    plugins: {
      legend: { labels: { color: '#D1D5DB', boxWidth: 12, padding: 15 } }
    }
  };

  return (
    <div className="clean-panel p-5 rounded-xl border border-[#332E29] space-y-5 shadow-xl bg-[#171513] text-gray-200">
      {/* 1. HEADER */}
      <div className="flex items-start justify-between border-b border-[#332E29] pb-3">
        <div>
          <h2 className="font-display text-xl font-bold text-white flex items-center gap-2">
            <BarChart2 className="w-5 h-5 text-gray-400" />
            Algorithm Performance
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Same scenario · Same constraints · Same objective · Measured execution
          </p>
        </div>
        <button onClick={onClose} aria-label="Close benchmark panel" className="p-1 hover:bg-[#26221D] rounded transition-colors text-gray-400 hover:text-white focus-visible:ring-2 focus-visible:ring-[#C6602E]">
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* 2. COMPARISON CONDITIONS (fairness) */}
      <div className="bg-[#1E1B18] border border-[#3A342E] rounded-lg p-3 flex flex-col gap-2">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
          <ShieldCheck size={14} className="text-[#6B9A57]" />
          Comparison Conditions
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-[#9FC589] font-mono">
          {['Same scenario', 'Same graph', 'Same jobs', 'Same fleet', 'Same constraints', 'Same objective', 'Same evaluation function'].map(cond => (
            <span key={cond}>✓ {cond}</span>
          ))}
        </div>
        <div className="text-[10px] text-gray-500 font-mono border-t border-[#332E29] pt-1.5">
          Documented solver configuration — seed: {config?.seed ?? benchmarkData.scenario_seed ?? '—'}
          {config?.population_size ? `, population: ${config.population_size}` : ''}
          {config?.max_iterations ? `, iterations: ${config.max_iterations}` : ''}
          {' '}(governs each stochastic algorithm's own search, not the fairness of the comparison itself)
        </div>
      </div>

      {/* 3. QPSO PERFORMANCE SUMMARY */}
      {qpsoSummary}

      {/* 3. VIEW / SCALE TOGGLES */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-1.5 bg-[#1E1B18] border border-[#3A342E] rounded-lg p-1">
          <button
            onClick={() => setBarScale('linear')}
            className={`px-2 py-1 rounded text-[10px] font-mono font-semibold transition-colors ${barScale === 'linear' ? 'bg-[#26221D] text-gray-200' : 'text-gray-500 hover:text-gray-300'}`}
          >
            Scale: Linear
          </button>
          <button
            onClick={() => setBarScale('log')}
            className={`px-2 py-1 rounded text-[10px] font-mono font-semibold transition-colors ${barScale === 'log' ? 'bg-[#26221D] text-gray-200' : 'text-gray-500 hover:text-gray-300'}`}
          >
            Scale: Log
          </button>
        </div>
        <div className="flex items-center gap-1.5 bg-[#1E1B18] border border-[#3A342E] rounded-lg p-1">
          <button
            onClick={() => setResultsView('bars')}
            className={`px-2.5 py-1 rounded text-[10px] font-mono font-semibold transition-colors flex items-center gap-1.5 ${resultsView === 'bars' ? 'bg-[#C6602E] text-white' : 'text-gray-500 hover:text-gray-300'}`}
          >
            <BarChart2 size={12} /> Side-by-Side Bars
          </button>
          <button
            onClick={() => setResultsView('table')}
            className={`px-2.5 py-1 rounded text-[10px] font-mono font-semibold transition-colors flex items-center gap-1.5 ${resultsView === 'table' ? 'bg-[#C6602E] text-white' : 'text-gray-500 hover:text-gray-300'}`}
          >
            <Table2 size={12} /> Data Table
          </button>
        </div>
      </div>

      {/* 3b. GROUPED BAR VIEW - execution speed and cost/quality side by
          side, same resultsArray the table below uses, just two bar groups
          instead of one. Log scale only affects bar width, never the
          printed numeric value. */}
      {resultsView === 'bars' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-[#1E1B18] border border-[#3A342E] rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-semibold text-gray-400 tracking-wider flex items-center gap-1.5">
                <Gauge size={13} /> EXECUTION SPEED (RUNTIME MS)
              </h3>
              <span className="text-[9px] font-mono text-[#5D7A9E] bg-[#5D7A9E]/10 rounded px-1.5 py-0.5">Lower is faster</span>
            </div>
            <div className="space-y-3">
              {resultsArray.map((res) => {
                const widthPct = barWidthPct(res.runtime_ms || 0, maxRuntime, barScale === 'log');
                return (
                  <div key={res.id} className="flex items-center gap-3">
                    <div className={`w-16 text-xs font-medium ${getAlgorithmColor(res.id).text}`}>
                      {res.algorithm || res.id.toUpperCase()}
                    </div>
                    <div className="flex-1 bg-[#26221D] h-2.5 rounded-full overflow-hidden relative">
                      <div
                        className={`h-full ${getAlgorithmColor(res.id).bg} rounded-full`}
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <div className="w-16 text-right font-mono text-sm text-gray-300 tabular-nums">
                      {res.runtime_ms.toFixed(0)}ms
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="bg-[#1E1B18] border border-[#3A342E] rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-semibold text-gray-400 tracking-wider flex items-center gap-1.5">
                <Zap size={13} /> SOLUTION COST &amp; QUALITY
              </h3>
              <span className="text-[9px] font-mono text-[#E8A93A] bg-[#E8A93A]/10 rounded px-1.5 py-0.5">Lower cost is better</span>
            </div>
            <div className="space-y-3">
              {resultsArray.map((res) => {
                const isBest = res.total_cost === minCost;
                const widthPct = barWidthPct(res.total_cost, maxCost, barScale === 'log');
                return (
                  <div key={res.id} className="flex items-center gap-3">
                    <div className={`w-16 text-xs font-medium ${getAlgorithmColor(res.id).text}`}>
                      {res.algorithm || res.id.toUpperCase()}
                    </div>
                    <div className="flex-1 bg-[#26221D] h-2.5 rounded-full overflow-hidden relative">
                      <div
                        className={`h-full ${getAlgorithmColor(res.id).bg} rounded-full ${isBest ? 'shadow-[0_0_8px_rgba(198,96,46,0.6)]' : ''}`}
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                    <div className="w-20 text-right font-mono text-sm text-gray-300 tabular-nums">
                      {res.total_cost.toFixed(1)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 4. BENCHMARK MATRIX TABLE */}
      {resultsView === 'table' && (
      <div className="bg-[#1E1B18] border border-[#3A342E] rounded-lg overflow-hidden">
        {results.exact && (
          <div className="px-4 py-2 text-[11px] text-[#E8A93A] bg-[#3A2E14]/30 border-b border-[#3A342E]">
            This scenario is small enough (≤10 jobs) for the exact solver to prove the true optimum - the Gap
            column below is a real optimality gap for every other algorithm, not just a comparison against
            whichever heuristic happened to do best.
          </div>
        )}
        <table className="w-full text-sm text-left">
          <thead className="text-xs text-gray-400 bg-[#26221D]/70 uppercase border-b border-[#3A342E]">
            <tr>
              <th className="px-4 py-3">Algorithm</th>
              <th className="px-4 py-3">Cost</th>
              <th className="px-4 py-3">Travel Time</th>
              <th className="px-4 py-3">Distance</th>
              <th className="px-4 py-3">Runtime</th>
              <th className="px-4 py-3" title="Iterations the solver actually recorded (convergence_history length), not the configured limit. Greedy is a single-pass construction, so it records one value.">Iterations</th>
              <th className="px-4 py-3">Feasible</th>
              <th className="px-4 py-3">{results.exact ? 'Gap vs Optimum' : 'Gap'}</th>
              {onPreviewAlgorithm && <th className="px-4 py-3">Map</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#3A342E]/50">
            {resultsArray.map((res) => {
              const isBest = res.total_cost === minCost;
              const gap = isBest ? 'BEST' : '+' + ((res.total_cost - minCost) / minCost * 100).toFixed(2) + '%';
              const isPreviewed = previewedAlgorithm === res.id;
              return (
                <tr
                  key={res.id}
                  onClick={onPreviewAlgorithm ? () => onPreviewAlgorithm(isPreviewed ? null : res.id) : undefined}
                  className={`${onPreviewAlgorithm ? 'cursor-pointer' : ''} hover:bg-[#26221D]/50 ${isBest ? 'bg-[#3A2318]/15' : ''} ${isPreviewed ? 'ring-1 ring-inset ring-[#C6602E]' : ''}`}
                >
                  <td className={`px-4 py-3 font-medium flex items-center gap-2 ${getAlgorithmColor(res.id).text}`}>
                    {res.algorithm || res.id.toUpperCase()}
                    {isBest && <Trophy className="w-3.5 h-3.5" />}
                  </td>
                  <td className={`px-4 py-3 font-mono tabular-nums ${isBest ? 'text-[#C6602E] font-bold' : 'text-gray-300'}`}>
                    {res.total_cost.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-400 tabular-nums">{res.total_travel_time.toFixed(1)}</td>
                  <td className="px-4 py-3 font-mono text-gray-400 tabular-nums">{res.total_distance.toFixed(1)}</td>
                  <td className="px-4 py-3 font-mono text-gray-400 tabular-nums">{res.runtime_ms}ms</td>
                  {/* Measured, not configured: how many values the solver
                      actually recorded. Greedy constructs a solution in one
                      pass and so records one - the configured iteration
                      count is never substituted here. */}
                  <td className="px-4 py-3 font-mono text-gray-400 tabular-nums">
                    {res.convergence_history?.length ? res.convergence_history.length : '—'}
                  </td>
                  <td className="px-4 py-3">
                    {res.is_feasible ? (
                      <span className="flex items-center text-[#6B9A57] gap-1"><CheckCircle2 className="w-4 h-4"/> ✓</span>
                    ) : (
                      <span className="flex items-center text-[#C1443B] gap-1"><XCircle className="w-4 h-4"/> ✗ ({res.constraint_violations})</span>
                    )}
                  </td>
                  <td className={`px-4 py-3 font-mono text-xs tabular-nums ${isBest ? 'text-[#C6602E]' : 'text-gray-500'}`}>
                    {gap}
                  </td>
                  {onPreviewAlgorithm && (
                    <td className="px-4 py-3 font-mono text-[10px] text-[#C6602E]">
                      {isPreviewed ? 'PREVIEWING' : 'View →'}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      )}

      {/* 5. CONVERGENCE CHART */}
      <div className="bg-[#1E1B18] border border-[#3A342E] rounded-lg p-4 space-y-2">
        <h3 className="text-xs font-semibold text-gray-400 tracking-wider">
          CONVERGENCE — best objective cost per recorded iteration
        </h3>
        <div className="h-44">
          <Line data={chartData} options={chartOptions} />
        </div>
        <p className="text-[10px] text-gray-500 font-mono">
          Every point is a value the solver recorded during this run. Greedy constructs its
          solution in a single pass, so it has no curve to plot and is not charted.
        </p>
      </div>

    </div>
  );
}
