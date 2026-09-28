import React, { useEffect, useState, useCallback, useRef } from 'react';
import { TrendingUp, Loader2, Play, Check } from 'lucide-react';
import { apiFetch } from '../api';
import Button from './ui/Button';
import { ALGORITHM_COLORS } from './BenchmarkPanel';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend
} from 'chart.js';
import { Line } from 'react-chartjs-2';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

function algoColor(id) {
  return ALGORITHM_COLORS[id]?.hex || '#9CA3AF';
}

// Reads/runs the real E2 convergence experiment
// (/api/experiments/E2_convergence[/run]) - same GET-on-mount + "Run Now"
// pattern as ScalabilityPanel.jsx (E3). The backend's convergence.csv rows
// (algorithm, iteration, best_cost) are grouped per algorithm here purely
// for charting; every plotted value is a real recorded best_cost, nothing
// interpolated or invented.
export default function ExperimentE2Panel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | not_run | error
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  // Confirms a re-run actually happened even though this sweep uses a fixed
  // seed, so the chart can come back byte-identical - without this, a
  // successful re-run and a silently-failed one look the same to the operator.
  const [justRan, setJustRan] = useState(false);
  const justRanTimer = useRef(null);
  useEffect(() => () => clearTimeout(justRanTimer.current), []);

  const load = useCallback(() => {
    return apiFetch('/api/experiments/E2_convergence')
      .then(res => {
        if (res.status === 404) {
          setStatus('not_run');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load convergence results');
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
    apiFetch('/api/experiments/E2_convergence/run', { method: 'POST' })
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
        <Loader2 size={14} className="animate-spin" /> Loading convergence results...
      </div>
    );
  }

  if (status === 'not_run' || status === 'error') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] text-gray-500 text-xs space-y-2 min-h-[120px] flex flex-col items-center justify-center text-center">
        <TrendingUp size={20} className="opacity-40" />
        <div className="font-semibold text-gray-400">CONVERGENCE (E2) — NOT YET RUN</div>
        <Button
          variant="secondary"
          size="sm"
          fullWidth={false}
          icon={running ? undefined : Play}
          loading={running}
          loadingText="Running real sweep..."
          onClick={handleRunNow}
        >
          Run Now
        </Button>
        {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
        <div className="max-w-[260px] font-mono text-[9px] leading-relaxed text-gray-600">
          Or run <span className="text-gray-400">python -m experiments.runner --experiment e2</span> from{' '}
          <span className="text-gray-400">backend/</span> directly.
        </div>
      </div>
    );
  }

  const rows = data.rows || [];
  const grouped = {};
  rows.forEach(r => {
    if (!grouped[r.algorithm]) grouped[r.algorithm] = [];
    grouped[r.algorithm].push(parseFloat(r.best_cost));
  });

  const maxLen = Math.max(0, ...Object.values(grouped).map(v => v.length));
  const chartData = {
    labels: Array.from({ length: maxLen }, (_, i) => i),
    datasets: Object.entries(grouped).map(([algo, values]) => ({
      label: algo.toUpperCase(),
      data: values,
      borderColor: algoColor(algo),
      backgroundColor: algoColor(algo),
      tension: 0.1,
      pointRadius: 0,
      borderWidth: 2
    }))
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 400, easing: 'easeOutQuad' },
    scales: {
      x: { grid: { color: '#332E29' }, ticks: { color: '#9CA3AF', maxTicksLimit: 10 } },
      y: { title: { display: true, text: 'Best Cost', color: '#9CA3AF' }, grid: { color: '#332E29' }, ticks: { color: '#9CA3AF' } }
    },
    plugins: { legend: { labels: { color: '#D1D5DB', boxWidth: 12, padding: 15 } } }
  };

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <TrendingUp size={14} className="text-[#5D7A9E]" />
          Convergence (E2)
        </div>
        <Button
          variant="secondary"
          size="sm"
          fullWidth={false}
          icon={running ? undefined : Play}
          loading={running}
          loadingText="Running..."
          title="Re-run the real convergence sweep"
          onClick={handleRunNow}
        >
          Run Now
        </Button>
      </div>
      {runError && <p className="text-[10px] text-[#E8918A]">{runError}</p>}
      {!runError && justRan && (
        <p className="text-[10px] text-[#6B9A57] flex items-center gap-1">
          <Check size={11} className="flex-shrink-0" /> Re-ran just now — same fixed seed, so an unchanged chart means it worked.
        </p>
      )}
      {chartData.datasets.length === 0 ? (
        <p className="text-[11px] text-gray-600">No rows in the stored results.</p>
      ) : (
        <div className="h-[220px]">
          <Line data={chartData} options={chartOptions} />
        </div>
      )}
    </div>
  );
}
