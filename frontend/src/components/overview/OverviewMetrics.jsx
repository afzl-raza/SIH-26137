import React from 'react';
import { Truck, Clock, Gauge, CheckCircle2, XCircle, Loader2, Sparkles } from 'lucide-react';

// Every value here comes from a real /api/problem/generate + /api/optimize
// run (see Overview.jsx) - the same endpoints and the same OptimizationResult
// shape Dashboard.jsx uses, plus a real Greedy (nearest-stop) run on the
// exact same scenario purely as a plain-language comparison baseline.
// Nothing is hardcoded; while a run is in flight, cards show a loading
// state instead of a placeholder number.
export default function OverviewMetrics({ scenario, result, baseline, loading, error }) {
  const ready = Boolean(scenario && result && baseline);

  // Only claim an improvement when it's real and worth stating - ties or
  // Greedy winning (it happens - see Task.md's E3 scalability findings)
  // both fall through to no headline stat, never a fabricated "0% better"
  // or a negative number dressed up as a win.
  const improvementPct = ready && baseline.total_cost > 0
    ? ((baseline.total_cost - result.total_cost) / baseline.total_cost) * 100
    : null;
  const hasRealImprovement = improvementPct != null && improvementPct > 0.5;

  const cards = ready
    ? [
        {
          icon: Truck, accent: '#5D7A9E', label: 'Fleet & stops',
          value: `${scenario.vehicles.length} vehicles`,
          detail: `${scenario.jobs.length} delivery stops to cover`,
        },
        {
          icon: Clock, accent: '#43D493', label: 'Time on the road',
          value: `${result.total_travel_time.toFixed(0)} min`,
          detail: `${result.total_distance.toFixed(1)} km driven, whole fleet combined`,
        },
        {
          icon: Gauge, accent: '#F5B942', label: 'Efficiency score',
          value: result.total_cost.toFixed(1),
          detail: `Lower is better - time, distance & traffic combined · solved in ${(result.runtime_ms / 1000).toFixed(2)}s`,
        },
        {
          icon: result.is_feasible ? CheckCircle2 : XCircle,
          accent: result.is_feasible ? '#43D493' : '#FF6868',
          label: 'Is this plan usable?',
          value: result.is_feasible ? 'Yes, ready to go' : 'Not yet',
          detail: result.is_feasible ? 'Every stop covered, no vehicle overloaded' : `${result.constraint_violations} thing(s) to fix first`,
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4">
      {ready && (
        <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-4 flex items-center gap-3 flex-wrap">
          <div className={`w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0 ${result.is_feasible ? 'bg-[#173A2D] text-[#43D493]' : 'bg-[#462122] text-[#FF6868]'}`}>
            {result.is_feasible ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
          </div>
          <div className="flex-1 min-w-[200px]">
            <div className="font-display font-bold text-[15px] text-[#FFF9F1]">
              {result.is_feasible ? 'Feasible route plan' : 'Route plan needs attention'}
            </div>
            <p className="text-[12px] text-[#B9B0A5] mt-0.5">
              {result.is_feasible
                ? 'Every delivery is assigned to a vehicle, and no one is overloaded or running late.'
                : `${result.constraint_violations} constraint violation(s) - see the Engineering Control Room for detail.`}
            </p>
          </div>
          {hasRealImprovement && (
            <div className="flex items-center gap-2 bg-[#FF7A1A]/10 border border-[#FF7A1A]/30 rounded-xl px-3.5 py-2 flex-shrink-0">
              <Sparkles size={16} className="text-[#FF7A1A]" />
              <div>
                <div className="font-display font-bold text-[18px] text-[#FF7A1A] leading-none">
                  {improvementPct.toFixed(0)}% more efficient
                </div>
                <div className="text-[10px] text-[#817970] mt-0.5">
                  than simply sending each vehicle to the nearest stop
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div data-tour="metrics" className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
    </div>
  );
}
