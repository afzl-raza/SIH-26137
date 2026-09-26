import React from 'react';
import { CheckCircle2, AlertTriangle, TrendingDown, TrendingUp } from 'lucide-react';
import { useCountUp } from '../../lib/useCountUp';
import { CORE_METRICS, fmt, pctChange } from './metrics';

const TRAVEL_TIME = CORE_METRICS.find(m => m.key === 'travel_time');

// The single dominant headline, driven by the same before/after pair as
// the rest of the page. A real % only appears when a real "before" exists;
// otherwise it states the real plan headline instead of inventing a
// baseline. A worse result is shown as worse (amber, "more"), not hidden.
export default function ExecutiveOutcome({ comparison }) {
  const { before, after, comparedWith } = comparison;
  const b = TRAVEL_TIME.get(before);
  const a = TRAVEL_TIME.get(after);
  const pct = before ? pctChange(b, a) : null;
  // Ticks the display from 0 to the real, already-computed percentage - a
  // rendering transition only, never an intermediate "measured" value.
  const animatedPct = useCountUp(pct != null ? Math.abs(pct) : null, 900);
  const better = pct != null && pct >= 0;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-6 text-center space-y-2">
      <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">Optimization Results</div>
      {pct != null ? (
        <>
          <div className={`font-display text-4xl sm:text-5xl font-bold tabular-nums flex items-center justify-center gap-2 ${better ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
            {better ? <TrendingDown size={32} /> : <TrendingUp size={32} />}
            {animatedPct.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-300 font-semibold uppercase tracking-wide">
            {better ? 'Less' : 'More'} Travel Time
          </div>
          <div className="text-[11px] text-gray-500 font-mono">
            {fmt(TRAVEL_TIME, b)} → {fmt(TRAVEL_TIME, a)}
          </div>
          <p className="text-xs text-gray-400 max-w-md mx-auto pt-1">
            Compared with {comparedWith}.
          </p>
        </>
      ) : (
        <>
          <div className="font-display text-2xl sm:text-3xl font-bold text-white flex items-center justify-center gap-2">
            {after.is_feasible
              ? <CheckCircle2 size={26} className="text-[#6B9A57]" />
              : <AlertTriangle size={26} className="text-[#E8A93A]" />}
            {after.is_feasible ? 'Feasible Route Plan' : 'Route Plan Ready - Needs Review'}
          </div>
          <div className="text-[11px] text-gray-500 font-mono">
            {after.routes?.length ?? 0} routes · {fmt(TRAVEL_TIME, a)} travel time
          </div>
        </>
      )}
    </div>
  );
}
