import React from 'react';
import { Truck, MapPin, Clock, Navigation, CheckCircle2, AlertTriangle, X, Waves } from 'lucide-react';
import IconButton from './ui/IconButton';

export default function VehicleInspector({ vehicle, route, scenario, onDeselect }) {
  if (!vehicle || !route) {
    return (
      <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-3 shadow-lg min-h-[300px] flex flex-col items-center justify-center text-gray-500">
        <Truck size={32} className="mb-2 opacity-50" />
        <h3 className="font-bold tracking-wider text-sm">VEHICLE INSPECTOR</h3>
        <p className="text-xs text-center max-w-[200px]">
          Click a vehicle route or marker on the map to inspect details.
        </p>
      </div>
    );
  }

  const loadPercent = vehicle.capacity > 0 
    ? Math.min(100, Math.round((route.total_demand / vehicle.capacity) * 100))
    : 0;
  
  const isOverCapacity = route.capacity_exceeded > 0;
  const isOverTime = route.time_exceeded > 0;
  // Per-stop timing (schedule.simulate_route, via VehicleRoute.stops) and each
  // job's own delivery window - both backend-computed, nothing derived here.
  const jobById = new Map((scenario?.jobs || []).map(j => [j.id, j]));
  const totalLate = route.late_jobs || 0;
  const hasLimitsExceeded = isOverCapacity || isOverTime || totalLate > 0;

  // borderColor set inline - .clean-card's own `border` shorthand rule is
  // equal-specificity and later in source order, so a Tailwind border-[...]
  // utility here would be silently overridden.
  //
  // Layout: the header stays outside the scroll region (always visible);
  // everything else (capacity/metrics/feasibility/route sequence) shares
  // ONE bounded, scrollable body instead of the card growing unbounded
  // (which pushed the whole sidebar/page very tall) or overflowing past a
  // cap with no overflow handling (which bled into the panel below).
  return (
    <div className="clean-card p-3.5 rounded-xl shadow-lg text-gray-300 flex flex-col max-h-[560px]" style={{ borderColor: '#5A3A22' }}>
      {/* 1. HEADER (always visible, not part of the scroll region) */}
      <div className="flex items-center justify-between border-b border-[#332E29] pb-2 mb-4 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div
            className="w-3 h-3 rounded-full"
            style={{ backgroundColor: vehicle.color || '#C6602E' }}
          />
          <h3 className="font-display font-bold text-white flex items-center gap-2">
            <Truck size={16} className="text-[#C6602E]" />
            VEHICLE {vehicle.id.toString().padStart(2, '0')}
          </h3>
        </div>
        <IconButton icon={X} iconSize={18} onClick={onDeselect} aria-label="Close vehicle inspector" />
      </div>

      {/* 2-4. SCROLLABLE BODY - min-h-0 is required for a flex child to
          actually shrink and scroll instead of growing to fit its content.
          Wrapped in a relative box so the fade cue below can pin to the
          bottom of the visible viewport regardless of scroll position. */}
      <div className="flex-1 min-h-0 relative">
      <div className="h-full overflow-y-auto pr-1 space-y-4">
      {/* 2. CAPACITY BAR */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-xs font-medium">
          <span className="text-gray-400 uppercase tracking-wider">Cargo Load</span>
          <span className={`${isOverCapacity ? 'text-[#C1443B]' : 'text-[#C6602E]'} font-mono tabular-nums`}>
            {loadPercent}% capacity
          </span>
        </div>
        <div className="h-2 w-full bg-[#26221D] rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${isOverCapacity ? 'bg-[#C1443B]' : 'bg-[#C6602E]'}`}
            style={{ width: `${loadPercent}%` }}
          />
        </div>
        <div className="text-right text-[10px] text-gray-500 font-mono tabular-nums">
          {route.total_demand.toFixed(1)} / {vehicle.capacity} units
        </div>
      </div>

      {/* 3. METRICS ROW */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="clean-panel p-2 rounded-lg border border-[#332E29] flex items-center gap-2">
          <MapPin size={14} className="text-[#5D7A9E]" />
          <div>
            <div className="text-gray-500 text-[10px] uppercase">Stops</div>
            <div className="font-mono text-gray-200 tabular-nums">{route.job_ids?.length || 0} stops</div>
          </div>
        </div>
        <div className="clean-panel p-2 rounded-lg border border-[#332E29] flex items-center gap-2">
          <Clock size={14} className="text-[#E8A93A]" />
          <div>
            <div className="text-gray-500 text-[10px] uppercase">Travel Time</div>
            <div className="font-mono text-gray-200 tabular-nums">{Math.round(route.route_travel_time)} min</div>
            {/* route.wait_time (schedule.simulate_route): total minutes waited
                across all stops, already folded into route_travel_time above -
                shown here so waiting is visible, not just baked into the total. */}
            {route.wait_time > 0 && (
              <div className="text-[9px] text-[#E8A93A] font-mono tabular-nums">incl. {route.wait_time.toFixed(0)}m wait</div>
            )}
          </div>
        </div>
        <div className="clean-panel p-2 rounded-lg border border-[#332E29] flex items-center gap-2">
          <Navigation size={14} className="text-[#6B9A57]" />
          <div>
            <div className="text-gray-500 text-[10px] uppercase">Distance</div>
            <div className="font-mono text-gray-200 tabular-nums">{route.route_distance.toFixed(1)} km</div>
          </div>
        </div>
        <div className={`clean-panel p-2 rounded-lg border flex items-center gap-2 ${route.congestion_delay > 0 ? 'border-[#5A4A22] bg-[#3A2E14]/30' : 'border-[#332E29]'}`}>
          <Waves size={14} className={route.congestion_delay > 0 ? 'text-[#E8A93A]' : 'text-gray-500'} />
          <div>
            <div className="text-gray-500 text-[10px] uppercase">Congestion</div>
            <div className={`font-mono tabular-nums ${route.congestion_delay > 0 ? 'text-[#E8A93A]' : 'text-gray-400'}`}>
              +{(route.congestion_delay || 0).toFixed(1)} min
            </div>
          </div>
        </div>
      </div>

      {/* 3b. FEASIBILITY STATUS */}
      <div className={`p-2 rounded-lg border flex items-center gap-2 ${hasLimitsExceeded ? 'border-[#5A2C26] bg-[#3A1C18]/30' : 'border-[#3A4A2E] bg-[#22301B]/30'}`}>
        {hasLimitsExceeded ? (
          <AlertTriangle size={14} className="text-[#C1443B]" />
        ) : (
          <CheckCircle2 size={14} className="text-[#6B9A57]" />
        )}
        <div className={`font-mono text-[11px] ${hasLimitsExceeded ? 'text-[#C1443B]' : 'text-[#6B9A57]'}`}>
          {totalLate > 0
            ? `${totalLate} JOB${totalLate === 1 ? '' : 'S'} LATE`
            : hasLimitsExceeded ? 'LIMIT EXCEEDED' : 'FEASIBLE'}
        </div>
      </div>

      {/* 4. VERTICAL ROUTE TIMELINE
          Lives in the shared scroll body above (no nested scrollbar of its
          own) - the label stays sticky to the top of that scroll viewport
          as you scroll past capacity/metrics/feasibility.

          The dot/line marker column is a normal-flow w-5 element per row
          (not an absolutely -left-positioned dot escaping into negative
          coordinates) - a negative offset previously placed the dot
          outside its own positioned ancestor, and combined with
          `overflow-y: auto` on a scroll container (which per the CSS
          overflow spec forces the *other* axis to compute as `auto` too
          when only one axis is set), that negative-x content was getting
          clipped, cutting the dots in half. */}
      <div className="text-xs text-gray-400 uppercase tracking-wider font-medium sticky top-0 bg-[#1E1B18] py-1 z-10">
        Route Sequence
      </div>

      <div className="relative space-y-3 pb-1">
        {/* Vertical connecting line - centered under the w-5 icon column */}
        <div className="absolute left-[9px] top-[10px] bottom-[10px] w-px bg-[#3A342E]"></div>

        {/* Start Depot */}
        <div className="relative flex items-center gap-2">
          <div className="relative z-10 w-5 h-5 flex items-center justify-center shrink-0">
            <div className="w-3 h-3 rounded-full border-2 border-[#C1443B] bg-[#1E1B18] flex items-center justify-center">
              <div className="w-1 h-1 bg-[#C1443B] rounded-full" />
            </div>
          </div>
          <div className="text-xs font-mono text-[#C1443B] font-bold">DEPOT (START)</div>
        </div>

        {/* Jobs - numbered by their real visit order (job_ids order IS the
            sequence the decoder/optimizer produced). Each row is a per-stop
            timing readout from VehicleRoute.stops (schedule.simulate_route):
            arrival, this job's own delivery window (if any), how long the
            vehicle waited, and how late it was - late rows in red, a wait in
            amber, exactly as reported by the backend. */}
        {route.job_ids?.map((jobId, idx) => {
          const stop = route.stops?.find(s => s.job_id === jobId);
          const job = jobById.get(jobId);
          const hasWindow = job?.ready_time != null && job?.due_time != null;
          const isLate = (stop?.lateness || 0) > 0;
          const hasWait = (stop?.wait || 0) > 0;

          return (
            <div key={`${jobId}-${idx}`} className="relative flex items-center gap-2">
              <div className="relative z-10 w-5 h-5 flex items-center justify-center shrink-0">
                <div className={`w-2.5 h-2.5 rounded-full border-2 bg-[#1E1B18] ${isLate ? 'border-[#C1443B]' : 'border-[#5D7A9E]'}`} />
              </div>
              <div className={`flex-1 clean-panel px-2 py-1.5 rounded border ${isLate ? 'border-[#5A2C26] bg-[#3A1C18]/30' : 'border-[#332E29]/60'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-gray-500 font-mono tabular-nums w-4">{idx + 1}.</span>
                    <span className="text-xs font-mono text-[#9AB3CC]">
                      JOB {jobId.toString().padStart(2, '0')}
                    </span>
                  </div>
                  {isLate ? (
                    <AlertTriangle size={14} className="text-[#C1443B]" />
                  ) : (
                    <CheckCircle2 size={14} className="text-[#6B9A57]/70" />
                  )}
                </div>
                {stop && (
                  <div className="mt-1 grid grid-cols-4 gap-x-1 text-[9px] font-mono">
                    <div>
                      <div className="uppercase text-gray-600">Arrival</div>
                      <div className="text-gray-300 tabular-nums">{stop.arrival.toFixed(0)}m</div>
                    </div>
                    <div>
                      <div className="uppercase text-gray-600">Window</div>
                      <div className="text-gray-300 tabular-nums">
                        {hasWindow ? `${job.ready_time.toFixed(0)}-${job.due_time.toFixed(0)}` : 'none'}
                      </div>
                    </div>
                    <div>
                      <div className="uppercase text-gray-600">Wait</div>
                      <div className={`tabular-nums ${hasWait ? 'text-[#E8A93A] font-semibold' : 'text-gray-300'}`}>
                        {hasWait ? `${stop.wait.toFixed(0)}m` : '—'}
                      </div>
                    </div>
                    <div>
                      <div className="uppercase text-gray-600">Late</div>
                      <div className={`tabular-nums ${isLate ? 'text-[#C1443B] font-semibold' : 'text-gray-300'}`}>
                        {isLate ? `+${stop.lateness.toFixed(0)}m` : '—'}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* End Depot */}
        <div className="relative flex items-center gap-2">
          <div className="relative z-10 w-5 h-5 flex items-center justify-center shrink-0">
            <div className="w-3 h-3 rounded-full border-2 border-[#C1443B] bg-[#1E1B18] flex items-center justify-center">
              <div className="w-1 h-1 bg-[#C1443B] rounded-full" />
            </div>
          </div>
          <div className="text-xs font-mono text-[#C1443B] font-bold">DEPOT (END)</div>
        </div>
      </div>
      </div>
      {/* Bottom fade - a "scroll for more" cue, pinned to the bottom of the
          scroll viewport (not the content), so it only reads as meaningful
          when there's actually more below. */}
      <div className="absolute bottom-0 left-0 right-1 h-6 bg-gradient-to-t from-[#1E1B18] to-transparent pointer-events-none" />
      </div>
    </div>
  );
}
