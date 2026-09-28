import React from 'react';
import { Info, Loader2, MousePointerClick } from 'lucide-react';
import NetworkMap from '../NetworkMap';

// The real map (frontend/src/components/NetworkMap.jsx) driven by a real
// generate+optimize run, with the same click-a-road-to-disrupt interaction
// Dashboard.jsx uses (onDisruptEdge -> POST /api/traffic/update -> real
// re-optimize) - not a decorative illustration and not a passive snapshot.
// It's still not a live vehicle feed (nothing here polls or streams), so
// the copy is careful to say "today's plan", not "live".
export default function OverviewLiveMap({ scenario, scenarioId, result, loading, refreshing, error, onDisruptEdge }) {
  return (
    <div data-tour="live-map" className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5 flex flex-col">
      <div className="flex items-start justify-between mb-1 flex-wrap gap-2">
        <div>
          <div className="flex items-center gap-1.5">
            <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Today's route plan</h2>
            <Info size={12} className="text-[#817970]" />
          </div>
          <p className="text-[11px] text-[#817970] mt-0.5 flex items-center gap-1.5 flex-wrap">
            <MousePointerClick size={11} className="text-[#FF7A1A] flex-shrink-0" />
            Click any road below to simulate a disruption and watch the plan adapt in real time.
          </p>
        </div>
        {result && (
          <span className="flex items-center gap-1.5 text-[10px] font-semibold text-[#43D493] bg-[#173A2D] rounded-full px-2.5 py-1 flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-[#43D493]" />
            {result.is_feasible ? 'Feasible' : 'Infeasible'} · {scenario?.vehicles?.length ?? 0} vehicles
          </span>
        )}
      </div>

      <div className="relative mt-3 rounded-xl overflow-hidden border border-[#3B342A] h-[340px] bg-[#100F0D]">
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
          <>
            <NetworkMap
              scenario={scenario}
              scenarioId={scenarioId}
              currentResult={result}
              loading={false}
              onDisruptEdge={onDisruptEdge}
              disruptDisabled={refreshing}
            />
            {refreshing && (
              <div className="absolute inset-0 bg-[#100F0D]/70 flex flex-col items-center justify-center gap-2 pointer-events-none z-[1300]">
                <Loader2 size={18} className="animate-spin text-[#FF7A1A]" />
                <span className="text-[11px] text-[#FFF9F1] font-semibold">Re-optimizing around the disruption…</span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
