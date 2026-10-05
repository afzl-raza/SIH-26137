import React, { useEffect, useState, useCallback } from 'react';
import { Target, Loader2, Play } from 'lucide-react';
import { apiFetch } from '../api';
import Button from './ui/Button';
import { ALLOW_LIVE_EXPERIMENT_RERUN } from '../lib/solverDefaults';

// Reads the real E7 experiment (/api/experiments/E7_optimality_gap): every
// algorithm against the exact solver's true optimum on small instances.
// All numbers come from summary.json as written by the experiment runner.
const LABELS = {
  exact: 'Exact solver (reference)',
  greedy: 'Greedy',
  pso: 'Classical PSO',
  ga: 'Genetic Algorithm',
  qpso: 'QPSO (no local search)',
  qpso_ls: 'QPSO + local search',
  qpso_memetic: 'QPSO + local search (memetic)'
};

export default function ExperimentE7Panel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | not_run | error
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);

  const load = useCallback(() => {
    return apiFetch('/api/experiments/E7_optimality_gap')
      .then(res => {
        if (res.status === 404) {
          setStatus('not_run');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load optimality gap results');
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

  useEffect(() => { load(); }, [load]);

  const handleRunNow = () => {
    setRunning(true);
    setRunError(null);
    apiFetch('/api/experiments/E7_optimality_gap/run', { method: 'POST' })
      .then(res => {
        if (!res.ok) throw new Error(`Run failed (${res.status})`);
        return res.json();
      })
      .then(json => { setData(json); setStatus('ready'); })
      .catch(err => setRunError(err.message))
      .finally(() => setRunning(false));
  };

  if (status === 'loading') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] flex items-center justify-center text-gray-500 text-xs gap-2 min-h-[120px]">
        <Loader2 size={14} className="animate-spin" /> Loading optimality gap results...
      </div>
    );
  }

  if (status === 'not_run' || status === 'error') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] text-gray-500 text-xs space-y-2 min-h-[120px] flex flex-col items-center justify-center text-center">
        <Target size={20} className="opacity-40" />
        <div className="font-semibold text-gray-400">GAP TO OPTIMUM (E7) — NOT YET RUN</div>
        {ALLOW_LIVE_EXPERIMENT_RERUN && (
          <Button variant="secondary" size="sm" fullWidth={false} icon={running ? undefined : Play}
            loading={running} loadingText="Running..." onClick={handleRunNow}>
            Run Now
          </Button>
        )}
        {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
        <div className="max-w-[260px] font-mono text-[9px] leading-relaxed text-gray-600">
          Run <span className="text-gray-400">python -m experiments.runner --experiment e7</span> from{' '}
          <span className="text-gray-400">backend/</span> to generate this evidence.
        </div>
      </div>
    );
  }

  const summary = data.result || {};
  const algos = summary.algorithms || {};
  const instances = summary.instances ?? 0;
  const rows = Object.entries(algos)
    .filter(([key]) => key !== 'exact' && algos[key].mean_gap_pct != null)
    .sort((a, b) => a[1].mean_gap_pct - b[1].mean_gap_pct);
  const worst = Math.max(...rows.map(([, v]) => v.mean_gap_pct), 0.0001);
  const cfg = data.config?.scenarios;
  const slack = instances - (summary.instances_where_optimum_is_strictly_feasible ?? instances);

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <Target size={14} className="text-[#6B9A57]" />
          Gap to True Optimum (E7)
        </div>
        {ALLOW_LIVE_EXPERIMENT_RERUN ? (
          <Button variant="secondary" size="sm" fullWidth={false} icon={running ? undefined : Play}
            loading={running} loadingText="Running..." title="Re-run the real optimality-gap experiment"
            onClick={handleRunNow}>
            Run Now
          </Button>
        ) : (
          <span className="text-[9px] font-mono text-gray-500 px-2 py-1 rounded border border-[#332E29] whitespace-nowrap"
            title="Live re-run is off on this hosted demo - run locally to regenerate">
            Pre-computed evidence
          </span>
        )}
      </div>
      {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}

      <p className="text-[10px] text-gray-500 leading-snug">
        Each algorithm vs the exact solver on {instances} small instances
        {cfg ? ` (${cfg.job_counts?.join(' / ')} deliveries, ${cfg.num_vehicles} vehicles)` : ''}.
        0% means it found the true best plan.
      </p>

      <div className="space-y-1.5">
        {rows.map(([key, v]) => (
          <div key={key} className="space-y-0.5">
            <div className="flex items-center justify-between text-[11px] font-mono">
              <span className="text-gray-300">{LABELS[key] || key}</span>
              <span className="text-gray-400 tabular-nums">
                {v.mean_gap_pct.toFixed(2)}% avg · optimum {v.found_optimum}/{v.runs}
              </span>
            </div>
            <div className="h-1.5 bg-[#26221D] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${key === 'qpso_ls' ? 'bg-[#C6602E]' : 'bg-[#5D7A9E]'}`}
                style={{ width: `${Math.max(2, (v.mean_gap_pct / worst) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <p className="text-[9px] text-gray-600 leading-snug">
        Worst single case, QPSO + local search: {algos.qpso_ls?.max_gap_pct?.toFixed(2)}%.
        {slack > 0 ? ` The penalties are soft: on ${slack} of ${instances} instances the true optimum overloads one vehicle slightly.` : ''}
        {' '}Instances above 10 deliveries have no exact reference.
      </p>
    </div>
  );
}
