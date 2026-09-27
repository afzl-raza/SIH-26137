import React from 'react';
import { Info, AlertTriangle, Loader2, GraduationCap } from 'lucide-react';

// Real alerts are derived from scenario.edges' backend-declared condition
// state (congestion_level/has_incident - see backend/models.py Edge; using
// the backend's own classification rather than re-deriving thresholds from
// traffic_factor in React, per this project's "no duplicated logic" rule).
// Overview.jsx's background run never applies a conditions layer or an
// incident (that only happens from the Dashboard), so every edge sits at
// free_flow here and this will normally show the empty state below - that's
// an honest reflection of "no conditions applied to this run", not a bug.
export default function OverviewAlerts({ scenario, result, loading, error }) {
  const affectedEdges = (scenario?.edges || []).filter(
    e => e.congestion_level !== 'free_flow' || e.has_incident
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-1.5">
            <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Traffic alerts</h2>
            <Info size={12} className="text-[#817970]" />
          </div>
          <button className="text-[11px] text-[#FF7A1A] font-semibold cursor-default">View all</button>
        </div>
        <p className="text-[11px] text-[#817970] mb-4">What changed and what to do next.</p>

        {loading && !scenario && (
          <div className="h-[80px] flex items-center justify-center">
            <Loader2 size={16} className="animate-spin text-[#817970]" />
          </div>
        )}

        {error && !scenario && (
          <p className="text-[12px] text-[#FF6868]">{error} - is the backend running?</p>
        )}

        {!loading && !error && scenario && affectedEdges.length === 0 && (
          <p className="text-[12px] text-[#817970]">
            No active alerts - today's scenario is running at free-flow conditions. Apply
            traffic conditions or trigger an incident from the Dashboard to see alerts here.
          </p>
        )}

        {affectedEdges.length > 0 && (
          <div className="flex flex-col gap-4">
            {affectedEdges.map(e => (
              <div key={`${e.source}-${e.destination}`} className="flex gap-2.5">
                <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5 bg-[#462122] text-[#FF6868]">
                  <AlertTriangle size={12} />
                </div>
                <div className="min-w-0">
                  <span className="text-[12.5px] font-semibold text-[#FFF9F1]">
                    {e.road_name || `Road ${e.source} → ${e.destination}`}
                  </span>
                  <p className="text-[11px] text-[#B9B0A5] mt-0.5">
                    {e.has_incident ? 'Incident reported · ' : ''}Congestion: {e.congestion_level.replace('_', ' ')} (×{e.traffic_factor.toFixed(2)})
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-[#4A2916]/40 border border-[#5A3620] rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-2 text-[#F5B942]">
          <GraduationCap size={16} />
          <h3 className="font-display font-bold text-[14px] text-[#FFF9F1]">Need help?</h3>
        </div>
        <p className="text-[11px] text-[#B9B0A5] mb-3">
          Take a 3-minute tour of planning your first route.
        </p>
        <button className="bg-[#FF7A1A] hover:bg-[#E86D10] text-[#100F0D] font-display font-bold text-[12px] px-3.5 py-2 rounded-lg transition-colors">
          Start guided tour
        </button>
      </div>
    </div>
  );
}
