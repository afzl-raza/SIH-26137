import React, { useEffect, useState, useCallback, useRef } from 'react';
import { AlertTriangle, Loader2, Play, Check } from 'lucide-react';
import { apiFetch } from '../api';
import Button from './ui/Button';
import { ALLOW_LIVE_EXPERIMENT_RERUN } from '../lib/solverDefaults';

// Reads/runs the real E4 traffic-disruption experiment
// (/api/experiments/E4_traffic_disruption[/run]) - same GET-on-mount +
// "Run Now" pattern as ScalabilityPanel.jsx (E3). All fields below come
// straight from the backend's result.json; before/after is only shown
// because the backend actually returns both `before_cost` and `after_cost`.
export default function ExperimentE4Panel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | not_run | error
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  // Confirms a re-run actually happened even though this experiment uses a
  // fixed seed, so the result can come back byte-identical - without this, a
  // successful re-run and a silently-failed one look the same to the operator.
  const [justRan, setJustRan] = useState(false);
  const justRanTimer = useRef(null);
  useEffect(() => () => clearTimeout(justRanTimer.current), []);

  const load = useCallback(() => {
    return apiFetch('/api/experiments/E4_traffic_disruption')
      .then(res => {
        if (res.status === 404) {
          setStatus('not_run');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load traffic disruption results');
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
    apiFetch('/api/experiments/E4_traffic_disruption/run', { method: 'POST', timeoutMs: 60000 })
      .then(async res => {
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || `Run failed (${res.status})`);
        }
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
        <Loader2 size={14} className="animate-spin" /> Loading traffic disruption results...
      </div>
    );
  }

  if (status === 'not_run' || status === 'error') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] text-gray-500 text-xs space-y-2 min-h-[120px] flex flex-col items-center justify-center text-center">
        <AlertTriangle size={20} className="opacity-40" />
        <div className="font-semibold text-gray-400">TRAFFIC DISRUPTION (E4) — NOT YET RUN</div>
        {ALLOW_LIVE_EXPERIMENT_RERUN ? (
          <>
            <Button
              variant="secondary"
              size="sm"
              fullWidth={false}
              icon={running ? undefined : Play}
              loading={running}
              loadingText="Running real disruption..."
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
          Run <span className="text-gray-400">python -m experiments.runner --experiment e4</span> from{' '}
          <span className="text-gray-400">backend/</span> {ALLOW_LIVE_EXPERIMENT_RERUN ? 'directly.' : 'to generate this evidence.'}
        </div>
      </div>
    );
  }

  const result = data.result || {};
  const hasBeforeAfter = typeof result.before_cost === 'number' && typeof result.after_cost === 'number';
  const delta = hasBeforeAfter ? result.after_cost - result.before_cost : null;

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2.5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
          <AlertTriangle size={14} className="text-[#C1443B]" />
          Traffic Disruption (E4)
        </div>
        {ALLOW_LIVE_EXPERIMENT_RERUN ? (
          <Button
            variant="secondary"
            size="sm"
            fullWidth={false}
            icon={running ? undefined : Play}
            loading={running}
            loadingText="Running..."
            title="Re-run the real disruption experiment"
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
          <Check size={11} className="flex-shrink-0" /> Re-ran just now — same fixed seed, so unchanged numbers mean it worked.
        </p>
      )}

      {result.target_edge && (
        <div className="text-[10px] text-gray-500 font-mono">
          Road {result.target_edge.source} → {result.target_edge.destination}
          {typeof result.congestion_factor === 'number' && ` · congestion ×${result.congestion_factor}`}
        </div>
      )}

      {hasBeforeAfter ? (
        <div className="grid grid-cols-3 gap-2 text-[11px] font-mono">
          <div className="clean-panel p-2 rounded border border-[#332E29]">
            <div className="text-gray-500 text-[9px] uppercase">Before</div>
            <div className="text-gray-200 tabular-nums">{result.before_cost.toFixed(2)}</div>
          </div>
          <div className="clean-panel p-2 rounded border border-[#332E29]">
            <div className="text-gray-500 text-[9px] uppercase">After</div>
            <div className="text-gray-200 tabular-nums">{result.after_cost.toFixed(2)}</div>
          </div>
          <div className="clean-panel p-2 rounded border border-[#332E29]">
            <div className="text-gray-500 text-[9px] uppercase">Δ Cost</div>
            <div className={delta >= 0 ? 'text-[#E8918A] tabular-nums' : 'text-[#6B9A57] tabular-nums'}>
              {delta >= 0 ? '+' : ''}{delta.toFixed(2)}
            </div>
          </div>
        </div>
      ) : (
        <p className="text-[11px] text-gray-600">Backend result did not include before/after cost.</p>
      )}

      <div className="text-[10px] text-gray-500 font-mono">
        {typeof result.reoptimization_runtime_ms === 'number' && `Re-optimized in ${result.reoptimization_runtime_ms.toFixed(0)}ms`}
        {Array.isArray(result.changed_vehicle_ids) && (
          <span> · {result.changed_vehicle_ids.length} vehicle(s) changed{result.changed_vehicle_ids.length > 0 ? `: ${result.changed_vehicle_ids.join(', ')}` : ''}</span>
        )}
      </div>
    </div>
  );
}
