import React, { useEffect, useState } from 'react';
import { Repeat, Loader2 } from 'lucide-react';

export default function ReproducibilityPanel() {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState('loading'); // loading | ready | not_run | error

  useEffect(() => {
    let cancelled = false;
    fetch('/api/experiments/E6_reproducibility')
      .then(res => {
        if (res.status === 404) {
          if (!cancelled) setStatus('not_run');
          return null;
        }
        if (!res.ok) throw new Error('Failed to load reproducibility results');
        return res.json();
      })
      .then(json => {
        if (json && !cancelled) {
          setData(json);
          setStatus('ready');
        }
      })
      .catch(() => { if (!cancelled) setStatus('error'); });
    return () => { cancelled = true; };
  }, []);

  if (status === 'loading') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] flex items-center justify-center text-gray-500 text-xs gap-2 min-h-[100px]">
        <Loader2 size={14} className="animate-spin" /> Loading reproducibility results...
      </div>
    );
  }

  if (status === 'not_run' || status === 'error') {
    return (
      <div className="clean-card p-4 rounded-xl border border-[#3A342E] text-gray-500 text-xs space-y-1 min-h-[100px] flex flex-col items-center justify-center text-center">
        <Repeat size={20} className="opacity-40 mb-1" />
        <div className="font-semibold text-gray-400">REPRODUCIBILITY — NOT YET RUN</div>
        <div className="max-w-[260px] font-mono text-[10px] leading-relaxed">
          Run <span className="text-gray-300">python -m experiments.runner --experiment e6</span> from{' '}
          <span className="text-gray-300">backend/</span> to generate this evidence.
        </div>
      </div>
    );
  }

  const summary = data.result || {};
  const seeds = data.config?.seeds || [];

  // Range bar geometry - every position is derived from real returned
  // fields (min/mean/max/std_cost), nothing invented. Guards against a
  // degenerate min===max range (division by zero -> NaN%).
  const { min_cost, max_cost, mean_cost, std_cost } = summary;
  const hasRange = [min_cost, max_cost, mean_cost].every(v => typeof v === 'number');
  const range = hasRange ? Math.max(1e-6, max_cost - min_cost) : 1;
  const pct = (v) => hasRange ? Math.min(100, Math.max(0, ((v - min_cost) / range) * 100)) : 0;
  const meanPct = hasRange ? pct(mean_cost) : 50;
  const bandLowPct = hasRange && typeof std_cost === 'number' ? pct(mean_cost - std_cost) : meanPct;
  const bandHighPct = hasRange && typeof std_cost === 'number' ? pct(mean_cost + std_cost) : meanPct;

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-2.5">
      <div className="flex items-center gap-2 text-xs font-semibold text-gray-300 uppercase tracking-wider">
        <Repeat size={14} className="text-[#5F8A80]" />
        Reproducibility (E6)
      </div>
      <div className="text-[10px] text-gray-500 font-mono">
        QPSO across {summary.seeds_tested ?? seeds.length} seeds, same scenario
      </div>
      <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
        <div className="clean-panel p-2 rounded border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase">Mean Cost</div>
          <div className="text-gray-200 tabular-nums">{summary.mean_cost?.toFixed(2) ?? '--'}</div>
        </div>
        <div className="clean-panel p-2 rounded border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase">Std. Dev.</div>
          <div className="text-gray-200 tabular-nums">{summary.std_cost?.toFixed(2) ?? '--'}</div>
        </div>
        <div className="clean-panel p-2 rounded border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase">Minimum</div>
          <div className="text-gray-200 tabular-nums">{summary.min_cost?.toFixed(2) ?? '--'}</div>
        </div>
        <div className="clean-panel p-2 rounded border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase">Maximum</div>
          <div className="text-gray-200 tabular-nums">{summary.max_cost?.toFixed(2) ?? '--'}</div>
        </div>
      </div>

      {/* Spread visualization - min/max track + mean marker + a soft
          +-std_cost band, all positions computed from the real numbers
          above, nothing new fetched or invented. */}
      {hasRange && (
        <div className="pt-1">
          <div className="relative h-2 rounded-full bg-[#26221D]">
            <div
              className="absolute top-0 h-2 rounded-full bg-[#C6602E]/15"
              style={{ left: `${bandLowPct}%`, width: `${Math.max(0, bandHighPct - bandLowPct)}%` }}
            />
            <div
              className="absolute top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-[#C6602E] ring-2 ring-[#1E1B18]"
              style={{ left: `${meanPct}%` }}
            />
          </div>
          <div className="flex justify-between text-[9px] text-gray-500 font-mono mt-1 tabular-nums">
            <span>{min_cost.toFixed(1)}</span>
            <span className="text-[#C6602E]">mean {mean_cost.toFixed(1)}</span>
            <span>{max_cost.toFixed(1)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
