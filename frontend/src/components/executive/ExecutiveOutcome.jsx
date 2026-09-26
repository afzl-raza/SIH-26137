import React from 'react';
import { CheckCircle2, TrendingDown, TrendingUp } from 'lucide-react';
import { CORE_METRICS, fmt, pctChange } from './metrics';

const TRAVEL_TIME = CORE_METRICS.find(m => m.key === 'travel_time');

// The single dominant headline. A real % only appears when a previous
// result actually exists (i.e. this is a re-optimize) - otherwise this
// states the real feasible-plan headline instead of inventing a baseline.
export default function ExecutiveOutcome({ currentResult, previousResult }) {
  const before = TRAVEL_TIME.get(previousResult);
  const after = TRAVEL_TIME.get(currentResult);
  const pct = previousResult ? pctChange(before, after) : null;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-6 text-center space-y-2">
      <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">Optimization Results</div>
      {pct != null ? (
        <>
          <div className={`font-display text-4xl sm:text-5xl font-bold tabular-nums flex items-center justify-center gap-2 ${pct >= 0 ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
            {pct >= 0 ? <TrendingDown size={32} /> : <TrendingUp size={32} />}
            {Math.abs(pct).toFixed(1)}%
          </div>
          <div className="text-sm text-gray-300 font-semibold uppercase tracking-wide">
            {pct >= 0 ? 'Lower' : 'Higher'} Travel Time
          </div>
          <div className="text-[11px] text-gray-500 font-mono">
            {fmt(TRAVEL_TIME, before)} → {fmt(TRAVEL_TIME, after)}
          </div>
          <p className="text-xs text-gray-400 max-w-md mx-auto pt-1">
            The optimized route plan {pct >= 0 ? 'reduces travel time' : 'changes travel time'} while serving the required stops.
          </p>
        </>
      ) : (
        <>
          <div className="font-display text-2xl sm:text-3xl font-bold text-white flex items-center justify-center gap-2">
            <CheckCircle2 size={26} className="text-[#6B9A57]" />
            Feasible Route Plan
          </div>
          <div className="text-[11px] text-gray-500 font-mono">
            {currentResult.routes?.length ?? 0} routes · {fmt(TRAVEL_TIME, after)} travel time
          </div>
          <p className="text-xs text-gray-400 max-w-md mx-auto pt-1">
            The route plan serves every required stop within a feasible schedule.
          </p>
        </>
      )}
    </div>
  );
}
