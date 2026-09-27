import React from 'react';
import { Info, MoreVertical, Loader2 } from 'lucide-react';

const STATUS_STYLE = {
  Optimized: { bg: '#173A2D', fg: '#43D493' },
  'Needs review': { bg: '#462122', fg: '#FF6868' },
};

// Every row is one vehicle's real route from the last /api/optimize result
// Overview.jsx fetched (see Overview.jsx) - no route naming, departure time,
// or before/after savings exist in that response, so those columns aren't
// shown here rather than being invented. Status is derived from the route's
// own real constraint fields (capacity_exceeded/time_exceeded/late_jobs).
export default function OverviewRecentRoutes({ scenario, result, loading, error }) {
  const routes = result?.routes || [];

  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Recent routes</h2>
          <Info size={12} className="text-[#817970]" />
        </div>
        <button className="text-[11px] text-[#FF7A1A] font-semibold cursor-default">View all routes</button>
      </div>
      <p className="text-[11px] text-[#817970] mb-4">
        {scenario ? `Today's optimized fleet (${routes.length} vehicles).` : "Today's optimized fleet."}
      </p>

      {loading && routes.length === 0 && (
        <div className="h-[104px] flex items-center justify-center">
          <Loader2 size={16} className="animate-spin text-[#817970]" />
        </div>
      )}

      {error && routes.length === 0 && (
        <p className="text-[12px] text-[#FF6868]">{error} - is the backend running?</p>
      )}

      {!loading && !error && routes.length === 0 && (
        <p className="text-[12px] text-[#817970]">No routes yet - trigger Optimize from the Dashboard to see results here.</p>
      )}

      {routes.length > 0 && (
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-[12px] min-w-[480px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-[#817970] border-b border-[#3B342A]">
                <th className="text-left font-semibold px-1 pb-2">Vehicle</th>
                <th className="text-left font-semibold px-1 pb-2">Stops</th>
                <th className="text-left font-semibold px-1 pb-2">Distance</th>
                <th className="text-left font-semibold px-1 pb-2">Travel time</th>
                <th className="text-left font-semibold px-1 pb-2">Status</th>
                <th className="w-6" />
              </tr>
            </thead>
            <tbody>
              {routes.map(r => {
                const needsReview = r.capacity_exceeded > 0 || r.time_exceeded > 0 || r.late_jobs > 0;
                const status = needsReview ? 'Needs review' : 'Optimized';
                const st = STATUS_STYLE[status];
                return (
                  <tr key={r.vehicle_id} className="border-b border-[#2A2620] last:border-0">
                    <td className="px-1 py-2.5">
                      <div className="text-[#FFF9F1] font-semibold">Vehicle {r.vehicle_id}</div>
                      <div className="text-[10px] text-[#817970]">{r.job_ids.length} stops</div>
                    </td>
                    <td className="px-1 text-[#B9B0A5]">{r.job_ids.length}</td>
                    <td className="px-1 text-[#B9B0A5]">{r.route_distance.toFixed(1)} km</td>
                    <td className="px-1 text-[#B9B0A5]">{r.route_travel_time.toFixed(0)} min</td>
                    <td className="px-1">
                      <span className="text-[10px] font-semibold rounded-full px-2 py-0.5" style={{ backgroundColor: st.bg, color: st.fg }}>
                        {status}
                      </span>
                    </td>
                    <td className="px-1 text-[#817970] cursor-default"><MoreVertical size={14} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
