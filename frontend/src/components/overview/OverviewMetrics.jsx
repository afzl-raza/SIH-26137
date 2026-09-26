import React from 'react';
import { Truck, Clock, Gauge, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

// Every value here comes from a real /api/problem/generate + /api/optimize
// run (see Overview.jsx) - the same endpoints and the same OptimizationResult
// shape Dashboard.jsx uses. Nothing is hardcoded; while that run is in
// flight each card shows a loading state instead of a placeholder number.
export default function OverviewMetrics({ scenario, result, loading, error }) {
  const cards = scenario && result
    ? [
        {
          icon: Truck, accent: '#5D7A9E', label: 'Fleet & stops',
          value: `${scenario.vehicles.length} vehicles`,
          detail: `${scenario.jobs.length} delivery stops`,
        },
        {
          icon: Clock, accent: '#43D493', label: 'Travel time',
          value: `${result.total_travel_time.toFixed(0)} min`,
          detail: `${result.total_distance.toFixed(1)} km driven, whole fleet`,
        },
        {
          icon: Gauge, accent: '#F5B942', label: 'Route cost',
          value: result.total_cost.toFixed(1),
          detail: `Time + distance + congestion · solved in ${(result.runtime_ms / 1000).toFixed(2)}s`,
        },
        {
          icon: result.is_feasible ? CheckCircle2 : XCircle,
          accent: result.is_feasible ? '#43D493' : '#FF6868',
          label: 'Plan status',
          value: result.is_feasible ? 'Feasible' : 'Infeasible',
          detail: result.is_feasible ? 'Every stop covered, no vehicle overloaded' : `${result.constraint_violations} constraint violation(s)`,
        },
      ]
    : [];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {loading && cards.length === 0 && [1, 2, 3, 4].map(i => (
        <div key={i} className="bg-[#211E1A] border border-[#3B342A] rounded-xl p-4 flex items-center justify-center h-[104px]">
          <Loader2 size={16} className="animate-spin text-[#817970]" />
        </div>
      ))}
      {error && cards.length === 0 && (
        <div className="col-span-full bg-[#462122]/40 border border-[#5A2A22] rounded-xl p-4 text-[12px] text-[#FF6868]">
          {error} - is the backend running?
        </div>
      )}
      {cards.map(m => (
        <div key={m.label} className="bg-[#211E1A] border border-[#3B342A] rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${m.accent}22`, color: m.accent }}>
              <m.icon size={14} />
            </div>
            <span className="text-[11px] text-[#B9B0A5]">{m.label}</span>
          </div>
          <div className="font-display font-bold text-[26px] text-[#FFF9F1] leading-none mb-1.5">
            {m.value}
          </div>
          <div className="text-[10px] text-[#817970]">{m.detail}</div>
        </div>
      ))}
    </div>
  );
}
