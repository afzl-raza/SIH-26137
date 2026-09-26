import React, { useEffect, useState, useCallback } from 'react';
import { TrendingUp, Loader2, Play } from 'lucide-react';
import { apiFetch } from '../api';
import Button from './ui/Button';

export default function ScalabilityPanel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | not_run | error
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);

  const load = useCallback(() => {
    return apiFetch('/api/experiments/E3_scalability')
      .then(res => {
        if (res.status === 404) {
          setStatus('not_run');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load scalability results');
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

  // Triggers the *real* E3 runner (same code path as the CLI) synchronously
  // on the backend, then reloads the real output - not a simulated run.
  const handleRunNow = () => {
    setRunning(true);
    setRunError(null);
    apiFetch('/api/experiments/E3_scalability/run', { method: 'POST' })
      .then(res => {
        if (!res.ok) throw new Error(`Run failed (${res.status})`);
        return res.json();
      })
      .then(json => {
        setData(json);
        setStatus('ready');
      })
      .catch(err => setRunError(err.message))
      .finally(() => setRunning(false));
  };

  if (status === 'loading') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] flex items-center justify-center text-gray-500 text-xs gap-2 min-h-[120px]">
        <Loader2 size={14} className="animate-spin" /> Loading scalability results...
      </div>
    );
  }

  if (status === 'not_run' || status === 'error') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] text-gray-500 text-xs space-y-2 min-h-[120px] flex flex-col items-center justify-center text-center">
        <TrendingUp size={20} className="opacity-40" />
        <div className="font-semibold text-gray-400">SCALABILITY — NOT YET RUN</div>
        <Button
          variant="secondary"
          size="sm"
          fullWidth={false}
          icon={running ? undefined : Play}
          loading={running}
          loadingText="Running real sweep (~10-20s)..."
          onClick={handleRunNow}
        >
          Run Now
        </Button>
        {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
        <div className="max-w-[260px] font-mono text-[9px] leading-relaxed text-gray-600">
          Or run <span className="text-gray-400">python -m experiments.runner --experiment e3</span> from{' '}
          <span className="text-gray-400">backend/</span> directly.
        </div>
      </div>
    );
  }

  const rows = data.rows || [];

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <TrendingUp size={14} className="text-[#5D7A9E]" />
          Scalability (E3)
        </div>
        <Button
          variant="secondary"
          size="sm"
          fullWidth={false}
          icon={running ? undefined : Play}
          loading={running}
          loadingText="Running..."
          title="Re-run the real scalability sweep"
          onClick={handleRunNow}
        >
          Run Now
        </Button>
      </div>
      {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
      <div className="text-[10px] text-gray-500 font-mono">
        Reduced solver budget — population {data.config?.solver?.population_size ?? '?'},
        iterations {data.config?.solver?.max_iterations ?? '?'} (not comparable to the live demo's cost values)
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11px] text-left font-mono">
          <thead className="text-gray-500 uppercase text-[9px]">
            <tr>
              <th className="py-1 pr-2">Nodes</th>
              <th className="py-1 pr-2">Jobs</th>
              <th className="py-1 pr-2">Algo</th>
              <th className="py-1 pr-2">Cost</th>
              <th className="py-1 pr-2">Runtime</th>
              <th className="py-1">Feasible</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#332E29]/60">
            {rows.map((row, idx) => (
              <tr key={idx} className="text-gray-300 tabular-nums">
                <td className="py-1 pr-2">{row.num_nodes}</td>
                <td className="py-1 pr-2">{row.num_jobs}</td>
                <td className="py-1 pr-2 uppercase">{row.algorithm}</td>
                <td className="py-1 pr-2">{parseFloat(row.total_cost).toFixed(1)}</td>
                <td className="py-1 pr-2">{parseFloat(row.runtime_ms).toFixed(0)}ms</td>
                <td className={row.is_feasible === 'True' ? 'py-1 text-[#6B9A57]' : 'py-1 text-[#C1443B]'}>
                  {row.is_feasible === 'True' ? '✓' : '✗'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
