import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Trophy, Loader2, Play, Check } from 'lucide-react';
import { apiFetch } from '../api';
import Button from './ui/Button';
import { ALGORITHM_COLORS } from './BenchmarkPanel';
import { ALLOW_LIVE_EXPERIMENT_RERUN } from '../lib/solverDefaults';

function algoColor(id) {
  return ALGORITHM_COLORS[id]?.hex || '#9CA3AF';
}

// Reads/runs the real E1 algorithm-comparison experiment
// (/api/experiments/E1_algorithm_comparison[/run] in backend/main.py) - same
// GET-on-mount + "Run Now" POST pattern as ScalabilityPanel.jsx (E3). Every
// row below is a `results.csv` line the backend actually wrote; the only
// client-side arithmetic is finding the minimum cost to highlight it.
export default function ExperimentE1Panel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | not_run | error
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  // Confirms a re-run actually happened even though this comparison uses a
  // fixed seed, so the table can come back byte-identical - without this, a
  // successful re-run and a silently-failed one look the same to the operator.
  const [justRan, setJustRan] = useState(false);
  const justRanTimer = useRef(null);
  useEffect(() => () => clearTimeout(justRanTimer.current), []);

  const load = useCallback(() => {
    return apiFetch('/api/experiments/E1_algorithm_comparison')
      .then(res => {
        if (res.status === 404) {
          setStatus('not_run');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load algorithm comparison results');
        return res.json();
      })
      .then(json => {
        if (json) {
          setData(json);
          setStatus('ready');
        }
      })
      .catch(() => setStatus('error'));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleRunNow = () => {
    setRunning(true);
    setRunError(null);
    clearTimeout(justRanTimer.current);
    setJustRan(false);
    apiFetch('/api/experiments/E1_algorithm_comparison/run', { method: 'POST' })
      .then(res => {
        if (!res.ok) throw new Error(`Run failed (${res.status})`);
        return res.json();
      })
      .then(json => {
        setData(json);
        setStatus('ready');
        setJustRan(true);
        justRanTimer.current = setTimeout(() => setJustRan(false), 4000);
      })
      .catch(err => setRunError(err.message))
      .finally(() => setRunning(false));
  };

  if (status === 'loading') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] flex items-center justify-center text-gray-500 text-xs gap-2 min-h-[120px]">
        <Loader2 size={14} className="animate-spin" /> Loading algorithm comparison...
      </div>
    );
  }

  if (status === 'not_run' || status === 'error') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] text-gray-500 text-xs space-y-2 min-h-[120px] flex flex-col items-center justify-center text-center">
        <Trophy size={20} className="opacity-40" />
        <div className="font-semibold text-gray-400">ALGORITHM COMPARISON (E1) — NOT YET RUN</div>
        {ALLOW_LIVE_EXPERIMENT_RERUN ? (
          <>
            <Button
              variant="secondary"
              size="sm"
              fullWidth={false}
              icon={running ? undefined : Play}
              loading={running}
              loadingText="Running real comparison..."
              onClick={handleRunNow}
            >
              Run Now
            </Button>
            {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
          </>
        ) : (
          <p className="max-w-[240px] text-[10px] leading-relaxed">
            Live re-run is off on this hosted demo — the full solver budget these experiments use can take minutes on the free hosting tier.
          </p>
        )}
        <div className="max-w-[260px] font-mono text-[9px] leading-relaxed text-gray-600">
          Run <span className="text-gray-400">python -m experiments.runner --experiment e1</span> from{' '}
          <span className="text-gray-400">backend/</span> {ALLOW_LIVE_EXPERIMENT_RERUN ? 'directly.' : 'to generate this evidence.'}
        </div>
      </div>
    );
  }

  const rows = data.rows || [];
  const minCost = rows.length > 0 ? Math.min(...rows.map(r => parseFloat(r.total_cost))) : null;

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <Trophy size={14} className="text-[#E8A93A]" />
          Algorithm Comparison (E1)
        </div>
        {ALLOW_LIVE_EXPERIMENT_RERUN ? (
          <Button
            variant="secondary"
            size="sm"
            fullWidth={false}
            icon={running ? undefined : Play}
            loading={running}
            loadingText="Running..."
            title="Re-run the real algorithm comparison"
            onClick={handleRunNow}
          >
            Run Now
          </Button>
        ) : (
          <span
            className="text-[9px] font-mono text-gray-500 px-2 py-1 rounded border border-[#332E29] whitespace-nowrap"
            title="Live re-run is off on this hosted demo (the full solver budget can take minutes on the free hosting tier) - run locally to regenerate"
          >
            Pre-computed evidence
          </span>
        )}
      </div>
      {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
      {!runError && justRan && (
        <p className="text-[10px] text-[#6B9A57] flex items-center gap-1">
          <Check size={11} className="flex-shrink-0" /> Re-ran just now — same fixed seed, so an unchanged table means it worked.
        </p>
      )}
      <div className="text-[10px] text-gray-500 font-mono">
        Population {data.config?.solver?.population_size ?? '?'}, iterations {data.config?.solver?.max_iterations ?? '?'} —
        same scenario/constraints across all algorithms
      </div>
      {rows.length === 0 ? (
        <p className="text-[11px] text-gray-600">No rows in the stored results.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px] text-left font-mono">
            <thead className="text-gray-500 uppercase text-[9px]">
              <tr>
                <th className="py-1 pr-2">Algorithm</th>
                <th className="py-1 pr-2">Cost</th>
                <th className="py-1 pr-2">Travel Time</th>
                <th className="py-1 pr-2">Distance</th>
                <th className="py-1 pr-2">Runtime</th>
                <th className="py-1">Feasible</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#332E29]/60">
              {rows.map((row, idx) => {
                const isBest = minCost !== null && parseFloat(row.total_cost) === minCost;
                return (
                  <tr key={idx} className="text-gray-300 tabular-nums">
                    <td className="py-1 pr-2 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: algoColor(row.algorithm_key) }} />
                      {row.algorithm}
                      {isBest && <span className="text-[#43D493] text-[9px] font-bold">BEST</span>}
                    </td>
                    <td className="py-1 pr-2">{parseFloat(row.total_cost).toFixed(2)}</td>
                    <td className="py-1 pr-2">{parseFloat(row.total_travel_time).toFixed(1)} min</td>
                    <td className="py-1 pr-2">{parseFloat(row.total_distance).toFixed(1)} km</td>
                    <td className="py-1 pr-2">{parseFloat(row.runtime_ms).toFixed(0)}ms</td>
                    <td className={row.is_feasible === 'True' ? 'py-1 text-[#6B9A57]' : 'py-1 text-[#C1443B]'}>
                      {row.is_feasible === 'True' ? '✓' : '✗'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
