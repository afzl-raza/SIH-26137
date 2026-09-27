import React from 'react';
import { Truck, AlertTriangle, ArrowRight } from 'lucide-react';

// Colors match the real congestion/incident styling used in the dashboard's
// NetworkMap (see lib/traffic.js) - free-flow green, incident red, route
// orange - so this illustration reads as the same product, not a separate
// marketing graphic with its own palette.
const FREE_FLOW = '#6B9A57';
const CONGESTED = '#C1443B';
const ROUTE = '#C6602E';

function RoutePanel({ label, description, pathColor, showIncident, showDetour }) {
  return (
    <div className="clean-card rounded-2xl p-5">
      <p className="text-[11px] font-mono font-semibold text-gray-300 uppercase tracking-wide">{label}</p>
      <p className="mt-1 text-xs text-gray-500 leading-snug">{description}</p>
      <svg viewBox="0 0 240 60" className="w-full mt-4" aria-hidden="true">
        {!showDetour && (
          <line x1="20" y1="30" x2="220" y2="30" stroke={pathColor} strokeWidth="3" strokeLinecap="round" />
        )}
        {showDetour && (
          <path
            d="M 20 30 L 75 30 Q 100 30 100 6 L 220 6"
            fill="none"
            stroke={pathColor}
            strokeWidth="3"
            strokeLinecap="round"
            className="landing-route-flow"
          />
        )}
        <circle cx="20" cy="30" r="7" fill="#171513" stroke="#E8A93A" strokeWidth="2" />
        <circle cx="220" cy={showDetour ? 6 : 30} r="7" fill="#171513" stroke={FREE_FLOW} strokeWidth="2" />
        {showIncident && (
          <>
            <circle cx="120" cy="30" r="9" fill={CONGESTED} className="landing-node-pulse" />
            <circle cx="120" cy="30" r="9" fill="none" stroke={CONGESTED} strokeWidth="1.5" opacity="0.5" />
          </>
        )}
      </svg>
      <div className="mt-3 flex items-center justify-between text-[10px] font-mono text-gray-500">
        <span className="flex items-center gap-1">
          <Truck className="w-3 h-3 text-[#E8A93A]" /> Depot
        </span>
        {showIncident && (
          <span className="flex items-center gap-1 text-[#E8918A]">
            <AlertTriangle className="w-3 h-3" /> Congestion
          </span>
        )}
        <span>Destination</span>
      </div>
    </div>
  );
}

export default function TrafficAdaptation() {
  return (
    <section id="traffic-adaptation" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="max-w-2xl mb-10 sm:mb-12 landing-fade-up">
        <h2 className="font-display font-bold text-2xl sm:text-3xl text-gray-50">
          Built to react to real traffic, not just plan around it
        </h2>
        <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed">
          A route that was optimal a minute ago can become the wrong choice the
          moment traffic changes. Q-DFRO notices and re-plans &mdash; it doesn&rsquo;t
          just hand a driver a fixed route and hope conditions hold.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr,auto,1fr,auto,1fr] gap-4 lg:gap-3 items-center landing-fade-up" style={{ animationDelay: '0.1s' }}>
        <RoutePanel
          label="Normal Network"
          description="Vehicle follows the optimized route."
          pathColor={ROUTE}
        />
        <ArrowRight className="hidden lg:block w-5 h-5 text-gray-600 justify-self-center" aria-hidden="true" />
        <RoutePanel
          label="Traffic Disruption"
          description="An incident raises travel time on this road."
          pathColor={ROUTE}
          showIncident
        />
        <ArrowRight className="hidden lg:block w-5 h-5 text-gray-600 justify-self-center" aria-hidden="true" />
        <RoutePanel
          label="Re-Optimized Route"
          description="Q-DFRO detours around the disruption."
          pathColor={FREE_FLOW}
          showIncident
          showDetour
        />
      </div>
    </section>
  );
}
