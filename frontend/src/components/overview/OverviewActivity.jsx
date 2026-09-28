import React from 'react';
import { Info, Loader2 } from 'lucide-react';
import { useToast } from '../ui/Toast';

// D0N is the same delivery-stop label the live map already uses (see
// NetworkMap.jsx's createJobMarkerIcon: `D${jobId < 10 ? '0'+jobId : jobId}`)
// - reused here rather than inventing a second label scheme for the same
// real job id.
function stopLabel(jobId) {
  return `D${jobId < 10 ? '0' + jobId : jobId}`;
}

// "Active Fleet Network State" - every field is computed from the same real
// /api/optimize result + scenario.vehicles Overview.jsx already fetched:
// status from whether the route actually has any assigned jobs (and the
// same capacity_exceeded/time_exceeded/late_jobs flags OverviewRecentRoutes
// uses), load % from the route's real total_demand against the vehicle's
// real capacity (models.py: VehicleRoute.total_demand, Vehicle.capacity),
// and the stop sequence from the route's own real job_ids. Nothing here is
// a placeholder value - a vehicle that is genuinely idle says IDLE / 0%,
// not a rounded-up filler number.
export default function OverviewActivity({ scenario, result, loading, error }) {
  const toast = useToast();
  const routes = result?.routes || [];
  const vehiclesById = new Map((scenario?.vehicles || []).map(v => [v.id, v]));

  const rows = routes.map(r => {
    const vehicle = vehiclesById.get(r.vehicle_id);
    const capacity = vehicle?.capacity ?? 0;
    const loadPct = capacity > 0 ? (r.total_demand / capacity) * 100 : 0;
    const needsReview = r.capacity_exceeded > 0 || r.time_exceeded > 0 || r.late_jobs > 0;
    const isIdle = r.job_ids.length === 0;
    const status = isIdle ? 'IDLE' : needsReview ? 'REVIEW' : 'EN ROUTE';

    let bounds;
    if (isIdle) {
      bounds = 'Standby at depot';
    } else if (r.job_ids.length === 1) {
      bounds = `Depot → ${stopLabel(r.job_ids[0])} → Depot`;
    } else {
      bounds = `Depot → ${stopLabel(r.job_ids[0])} … ${stopLabel(r.job_ids[r.job_ids.length - 1])} (${r.job_ids.length} stops) → Depot`;
    }

    return { vehicleId: r.vehicle_id, status, isIdle, needsReview, loadPct, totalDemand: r.total_demand, capacity, bounds };
  });

  const statusColor = (row) => (row.isIdle ? 'text-[#817970]' : row.needsReview ? 'text-[#FF6868]' : 'text-[#43D493]');

  return (
    <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Fleet status</h2>
          <Info size={12} className="text-[#817970]" />
        </div>
        <button
          onClick={() => toast("Fleet history isn't built yet", { tone: 'error', detail: 'Only today\'s current route assignments are shown here - there is no saved history in this prototype.' })}
          className="text-[11px] text-[#FF7A1A] font-semibold hover:text-[#E86D10] transition-colors"
        >
          See all
        </button>
      </div>
      <p className="text-[11px] text-[#817970] mb-4">Real load and route bounds, straight from today's optimize result.</p>

      {loading && rows.length === 0 && (
        <div className="h-[104px] flex items-center justify-center">
          <Loader2 size={16} className="animate-spin text-[#817970]" />
        </div>
      )}

      {error && rows.length === 0 && (
        <p className="text-[12px] text-[#FF6868]">{error} - is the backend running?</p>
      )}

      {!loading && !error && rows.length === 0 && (
        <p className="text-[12px] text-[#817970]">No fleet data yet - trigger Optimize from the Dashboard.</p>
      )}

      {rows.length > 0 && (
        <div className="flex flex-col gap-1.5">
          {rows.map(row => (
            <div
              key={row.vehicleId}
              className="bg-[#171512] border border-[#3B342A] rounded-lg px-3 py-2 font-mono text-[11px] leading-relaxed overflow-x-auto whitespace-nowrap"
            >
              <span className="text-[#5D7A9E] font-semibold">[V{row.vehicleId}]</span>{' '}
              <span className={`font-semibold ${statusColor(row)}`}>{row.status}</span>
              <span className="text-[#4A4238]"> · </span>
              <span className="text-[#817970]">Load</span>{' '}
              <span className="text-[#FFF9F1]">{row.loadPct.toFixed(1)}%</span>{' '}
              <span className="text-[#817970]">({row.totalDemand.toFixed(1)}/{row.capacity.toFixed(1)} units)</span>
              <span className="text-[#4A4238]"> · </span>
              <span className="text-[#B9B0A5]">{row.bounds}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
