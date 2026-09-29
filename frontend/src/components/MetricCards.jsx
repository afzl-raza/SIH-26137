import React, { useMemo } from 'react';
import { Clock, Navigation, Cpu, CheckCircle2, AlertTriangle, TrendingDown, TrendingUp, ArrowRight, GitBranch, Info, Hourglass } from 'lucide-react';
import { useCountUp } from '../lib/useCountUp';

export default function MetricCards({ result, previousResult, weights, manifest, completedAt }) {
  // Hooks must run unconditionally on every render, before the early return
  // below - useCountUp itself tolerates a null target.
  const animatedCost = useCountUp(result?.total_cost);
  const animatedTravelTime = useCountUp(result?.total_travel_time);
  const animatedDistance = useCountUp(result?.total_distance);

  const routeChangeCount = useMemo(() => {
    if (!previousResult?.routes || !result?.routes) return null;
    const prevByVehicle = new Map(
      previousResult.routes.map(r => [r.vehicle_id, JSON.stringify(r.job_ids)])
    );
    return result.routes.filter(
      r => prevByVehicle.get(r.vehicle_id) !== JSON.stringify(r.job_ids)
    ).length;
  }, [result, previousResult]);

  // Sum of VehicleRoute.late_jobs (schedule.simulate_route) across the fleet.
  // Always 0 when time windows are off, since no stop ever carries a
  // due_time to miss.
  const lateDeliveries = useMemo(
    () => (result?.routes || []).reduce((sum, r) => sum + (r.late_jobs || 0), 0),
    [result]
  );

  if (!result) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 sm:gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div key={i} className="clean-card p-4 flex flex-col items-center justify-center text-gray-500">
            <span className="text-2xl font-mono">--</span>
          </div>
        ))}
      </div>
    );
  }

  const costChange = previousResult
    ? ((previousResult.total_cost - result.total_cost) / previousResult.total_cost) * 100
    : 0;

  const isImproved = costChange > 0;
  const isWorse = costChange < 0;

  const weightsFormula = weights
    ? `Cost = ${weights.travel_time_weight} · Time + ${weights.distance_weight} · Distance + ${weights.gamma} · Congestion${weights.penalty_weight ? ` (penalty ${weights.penalty_weight})` : ''}`
    : null;

  return (
    <div className="flex flex-col gap-6">
      {/* Headline result - the same "impossible to miss" treatment
          Overview's hero banner already uses for its own real efficiency
          number, ported here for the real before/after re-optimize delta.
          Only appears once there's an actual previousResult to compare
          against (i.e. after a real re-optimize, not the very first run) -
          shows the honest direction (down is good, up is a real
          regression) rather than only ever announcing improvement. */}
      {previousResult && costChange !== 0 && (
        <div className={`clean-panel rounded-xl p-5 sm:p-6 border flex flex-col sm:flex-row items-center gap-4 sm:gap-6 ${
          isImproved ? 'border-[#6B9A57]/30 bg-[#6B9A57]/5' : 'border-[#E8A93A]/30 bg-[#E8A93A]/5'
        }`}>
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider">
            {result.is_feasible ? (
              <span className="flex items-center gap-1 text-[#6B9A57]"><CheckCircle2 size={14} /> Optimization Complete</span>
            ) : (
              <span className="flex items-center gap-1 text-[#C1443B]"><AlertTriangle size={14} /> Optimization Complete</span>
            )}
            <span className="text-gray-600">·</span>
            <span className={result.is_feasible ? 'text-[#6B9A57]' : 'text-[#C1443B]'}>
              {result.is_feasible ? 'Feasible' : `${result.constraint_violations || 0} violation(s)`}
            </span>
          </div>
          <div className="flex-1 flex flex-col sm:flex-row items-center gap-4 sm:gap-8 w-full">
            <div className="text-center sm:text-left flex-shrink-0">
              <div
                className="font-display text-4xl sm:text-5xl font-bold tabular-nums leading-none"
                style={{ color: isImproved ? '#10b981' : '#E8A93A' }}
              >
                {isImproved ? '' : '+'}{Math.abs(costChange).toFixed(1)}%
              </div>
              <div className="text-gray-500 text-[11px] uppercase tracking-wider mt-1.5">
                Cost {isImproved ? 'Reduction' : 'Increase'}
              </div>
            </div>
            <div className="hidden sm:block w-px h-10 bg-[#332E29] flex-shrink-0" />
            <div className="flex items-center gap-6 sm:gap-8 font-mono text-sm">
              <div className="text-center sm:text-left">
                <div className="text-gray-500 text-[10px] uppercase tracking-wider">Before</div>
                <div className="text-gray-400 tabular-nums">{previousResult.total_cost?.toFixed(1)}</div>
              </div>
              <ArrowRight size={16} className="text-gray-600 flex-shrink-0" />
              <div className="text-center sm:text-left">
                <div className="text-gray-500 text-[10px] uppercase tracking-wider">After</div>
                <div className="text-white font-bold tabular-nums">{result.total_cost?.toFixed(1)}</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Solver Output — one dense row, cost given slightly more weight
          via a left accent border rather than a separate oversized block */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-3 sm:gap-4">
        {/* Cost (hero, but sized like its siblings) */}
        {/* borderLeft set inline, not via a Tailwind border-l-* utility -
            .clean-card's own `border` shorthand rule is equal-specificity
            and later in source order, so a utility class here would be
            silently overridden; inline style always wins. */}
        <div className="clean-card p-4 flex flex-col" style={{ borderLeft: '3px solid #C6602E' }}>
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-[#C6602E] text-xs font-bold tracking-wider uppercase">Solver Output</span>
            {weightsFormula && (
              <span title={weightsFormula} className="text-gray-500 hover:text-gray-300 cursor-help">
                <Info size={11} />
              </span>
            )}
          </div>
          <span className="font-display text-2xl font-bold text-white tabular-nums">{animatedCost?.toFixed(2)}</span>
          <span className="text-gray-500 text-[10px] mt-0.5 uppercase tracking-wide">Total Cost</span>
          {previousResult && costChange !== 0 && (
            <span className={`flex items-center text-[11px] font-mono mt-1 ${isImproved ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
              {isImproved ? <TrendingDown size={13} className="mr-1"/> : <TrendingUp size={13} className="mr-1"/>}
              {isImproved ? `↓ ${Math.abs(costChange).toFixed(1)}%` : `↑ ${Math.abs(costChange).toFixed(1)}%`}
            </span>
          )}
        </div>

        {/* Travel Time */}
        <div className="clean-card p-4 flex items-start gap-3">
          <div className="p-2 rounded bg-[#5F8A80]/10 text-[#5F8A80]">
            <Clock size={20} />
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-xs uppercase tracking-wider mb-1">Travel Time</span>
            <span className="font-display text-lg text-white tabular-nums">{animatedTravelTime?.toFixed(1) || '0'} min</span>
          </div>
        </div>

        {/* Distance */}
        <div className="clean-card p-4 flex items-start gap-3">
          <div className="p-2 rounded bg-[#5D7A9E]/10 text-[#5D7A9E]">
            <Navigation size={20} />
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-xs uppercase tracking-wider mb-1">Distance</span>
            <span className="font-display text-lg text-white tabular-nums">{animatedDistance?.toFixed(1) || '0'} km</span>
          </div>
        </div>

        {/* Runtime */}
        <div className="clean-card p-4 flex items-start gap-3">
          <div className="p-2 rounded bg-[#8C5A6E]/10 text-[#8C5A6E]">
            <Cpu size={20} />
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-xs uppercase tracking-wider mb-1">Runtime</span>
            <span className="font-display text-lg text-white tabular-nums">{((result.runtime_ms || 0) / 1000).toFixed(2)} s</span>
          </div>
        </div>

        {/* Feasibility */}
        <div className="clean-card p-4 flex items-start gap-3">
          <div className={`p-2 rounded ${result.is_feasible ? 'bg-[#6B9A57]/10 text-[#6B9A57]' : 'bg-[#C1443B]/10 text-[#C1443B]'}`}>
            {result.is_feasible ? <CheckCircle2 size={20} /> : <AlertTriangle size={20} />}
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-xs uppercase tracking-wider mb-1">Feasibility</span>
            <span className={`font-display text-lg font-bold tabular-nums ${result.is_feasible ? 'text-[#6B9A57]' : 'text-[#C1443B]'}`}>
              {result.is_feasible ? '✓ VALID' : `${result.constraint_violations || 0} VIOLATIONS`}
            </span>
          </div>
        </div>

        {/* Late Deliveries (CVRPTW) - sum of VehicleRoute.late_jobs across
            the fleet. Always 0/green when time windows are off. */}
        <div className="clean-card p-4 flex items-start gap-3">
          <div className={`p-2 rounded ${lateDeliveries > 0 ? 'bg-[#C1443B]/10 text-[#C1443B]' : 'bg-[#6B9A57]/10 text-[#6B9A57]'}`}>
            <Hourglass size={20} />
          </div>
          <div className="flex flex-col">
            <span className="text-gray-400 text-xs uppercase tracking-wider mb-1">Late Deliveries</span>
            <span className={`font-display text-lg font-bold tabular-nums ${lateDeliveries > 0 ? 'text-[#C1443B]' : 'text-[#6B9A57]'}`}>
              {lateDeliveries}
            </span>
          </div>
        </div>
      </div>

      {/* Before / After Comparison */}
      {previousResult && (
        <div className="clean-panel p-6 mt-2 border border-[#332E29] rounded-lg">
          <h3 className="font-display text-sm font-semibold text-gray-300 uppercase tracking-wider mb-4">Before → After Comparison</h3>
          
          <div className="flex flex-col md:flex-row items-center justify-between gap-6 relative">
            {/* Before Column */}
            <div className="flex-1 clean-card p-4 w-full">
              <span className="block text-gray-500 text-xs font-bold uppercase mb-3">Before</span>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Travel Time:</span>
                  <span className="font-mono text-gray-300">{previousResult.total_travel_time?.toFixed(1)} min</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Total Cost:</span>
                  <span className="font-mono text-gray-300">{previousResult.total_cost?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Distance:</span>
                  <span className="font-mono text-gray-300">{previousResult.total_distance?.toFixed(1)} km</span>
                </div>
              </div>
            </div>

            {/* Divider / Arrow */}
            <div className="text-gray-600 flex-shrink-0">
              <ArrowRight size={24} className="hidden md:block" />
              <ArrowRight size={24} className="block md:hidden transform rotate-90" />
            </div>

            {/* After Column */}
            <div className="flex-1 clean-card p-4 w-full">
              <span className="block text-[#C6602E] text-xs font-bold uppercase mb-3">After</span>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Travel Time:</span>
                  <span className="font-mono text-white">{result.total_travel_time?.toFixed(1)} min</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Total Cost:</span>
                  <span className="font-mono text-white">{result.total_cost?.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Distance:</span>
                  <span className="font-mono text-white">{result.total_distance?.toFixed(1)} km</span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            {costChange !== 0 && (
              <div className={`px-4 py-2 rounded-full border text-sm font-mono font-bold flex items-center gap-2 ${
                isImproved ? 'bg-[#6B9A57]/10 border-[#6B9A57]/20 text-[#6B9A57]' : 'bg-[#E8A93A]/10 border-[#E8A93A]/20 text-[#E8A93A]'
              }`}>
                {isImproved ? <TrendingDown size={16} /> : <TrendingUp size={16} />}
                COST CHANGE {isImproved ? '↓' : '↑'} {Math.abs(costChange).toFixed(1)}%
              </div>
            )}
            {routeChangeCount != null && (
              <div className="px-4 py-2 rounded-full border border-[#C6602E]/20 bg-[#C6602E]/10 text-[#C6602E] text-sm font-mono font-bold flex items-center gap-2">
                <GitBranch size={16} />
                {routeChangeCount} {routeChangeCount === 1 ? 'ROUTE' : 'ROUTES'} CHANGED
              </div>
            )}
          </div>
        </div>
      )}

      {/* Reproducibility footer - directly under the results, not buried in
          Advanced Settings. Every field is either the manifest the backend
          already reads back from stored state, or a timestamp captured on
          this client the moment the result actually arrived - nothing here
          is invented. */}
      {manifest && (
        <div className="clean-card px-4 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-1 text-[10px] font-mono text-gray-500">
          <span className="text-gray-600 uppercase tracking-wider font-bold">Run:</span>
          <span>
            <span className="text-gray-600">hash</span>{' '}
            <span className="text-gray-300">{manifest.scenario_hash}</span>
          </span>
          <span>
            <span className="text-gray-600">scenario seed</span>{' '}
            <span className="text-gray-300">{manifest.seed}</span>
          </span>
          {manifest.solver?.seed != null && manifest.solver.seed !== manifest.seed && (
            <span>
              <span className="text-gray-600">solver seed</span>{' '}
              <span className="text-gray-300">{manifest.solver.seed}</span>
            </span>
          )}
          {manifest.solver?.algorithm && (
            <span>
              <span className="text-gray-600">algorithm</span>{' '}
              <span className="text-gray-300">{manifest.solver.algorithm}</span>
            </span>
          )}
          {manifest.solver?.population_size != null && (
            <span>
              <span className="text-gray-600">pop/rounds</span>{' '}
              <span className="text-gray-300">{manifest.solver.population_size}/{manifest.solver.max_iterations}</span>
            </span>
          )}
          {completedAt && (
            <span>
              <span className="text-gray-600">completed</span>{' '}
              <span className="text-gray-300">{new Date(completedAt).toLocaleTimeString()}</span>
            </span>
          )}
        </div>
      )}
    </div>
  );
}
