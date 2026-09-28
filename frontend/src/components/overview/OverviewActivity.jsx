import React from 'react';
import { Info, Truck, Loader2 } from 'lucide-react';
import { useToast } from '../ui/Toast';

// Each entry is one vehicle's real route from the last /api/optimize result
// Overview.jsx fetched - no teammate/join/detour events or CO2 figures exist
// anywhere in the backend, so those (previously static) items are gone
// rather than replaced with a different invented substitute.
export default function OverviewActivity({ scenario, result, loading, error }) {
  const toast = useToast();
  const routes = result?.routes || [];

  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Activity</h2>
          <Info size={12} className="text-[#817970]" />
        </div>
        <button
          onClick={() => toast("Activity history isn't built yet", { tone: 'error', detail: 'Only today\'s route results are shown here - there is no saved activity log in this prototype.' })}
          className="text-[11px] text-[#FF7A1A] font-semibold hover:text-[#E86D10] transition-colors"
        >
          See all
        </button>
      </div>
      <p className="text-[11px] text-[#817970] mb-4">Today's route results, per vehicle.</p>

      {loading && routes.length === 0 && (
        <div className="h-[104px] flex items-center justify-center">
          <Loader2 size={16} className="animate-spin text-[#817970]" />
        </div>
      )}

      {error && routes.length === 0 && (
        <p className="text-[12px] text-[#FF6868]">{error} - is the backend running?</p>
      )}

      {!loading && !error && routes.length === 0 && (
        <p className="text-[12px] text-[#817970]">No activity yet - trigger Optimize from the Dashboard.</p>
      )}

      {routes.length > 0 && (
        <div className="flex flex-col gap-3.5">
          {routes.map(r => {
            const needsReview = r.capacity_exceeded > 0 || r.time_exceeded > 0 || r.late_jobs > 0;
            return (
              <div key={r.vehicle_id} className="flex items-center gap-2.5">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: needsReview ? '#46212233' : '#43D49322', color: needsReview ? '#FF6868' : '#43D493' }}
                >
                  <Truck size={13} />
                </div>
                <div className="min-w-0">
                  <div className="text-[12px] text-[#FFF9F1]">
                    Vehicle {r.vehicle_id} route {needsReview ? 'needs review' : 'optimized'}
                  </div>
                  <div className="text-[10px] text-[#817970]">
                    {r.job_ids.length} stops · {r.route_distance.toFixed(1)} km · {r.route_travel_time.toFixed(0)} min
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
