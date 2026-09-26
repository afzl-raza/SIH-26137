import React from 'react';
import { Info, Loader2 } from 'lucide-react';
import NetworkMap from '../NetworkMap';

// The real map (frontend/src/components/NetworkMap.jsx) driven by a real
// generate+optimize run - not a decorative illustration. It's a one-time
// snapshot taken when this page loaded, not a live feed, so the label says
// that rather than implying continuous updates.
export default function OverviewLiveMap({ scenario, result, loading, error }) {
  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5 flex flex-col">
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-1.5">
            <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Today's route plan</h2>
            <Info size={12} className="text-[#817970]" />
          </div>
          <p className="text-[11px] text-[#817970] mt-0.5">
            A real optimized plan for today's demo scenario - not a live vehicle feed.
          </p>
        </div>
        {result && (
          <span className="flex items-center gap-1.5 text-[10px] font-semibold text-[#43D493] bg-[#173A2D] rounded-full px-2.5 py-1">
            <span className="w-1.5 h-1.5 rounded-full bg-[#43D493]" />
            {result.is_feasible ? 'Feasible' : 'Infeasible'} · {scenario?.vehicles?.length ?? 0} vehicles
          </span>
        )}
      </div>

      <div className="mt-3 rounded-xl overflow-hidden border border-[#3B342A] h-[340px] bg-[#100F0D]">
        {loading && (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 text-[#817970]">
            <Loader2 size={20} className="animate-spin" />
            <span className="text-[11px]">Generating and optimizing today's plan…</span>
          </div>
        )}
        {!loading && error && (
          <div className="w-full h-full flex items-center justify-center text-[12px] text-[#FF6868] px-6 text-center">
            {error}
          </div>
        )}
        {!loading && !error && scenario && result && (
          <NetworkMap scenario={scenario} currentResult={result} loading={false} />
        )}
      </div>
    </div>
  );
}
