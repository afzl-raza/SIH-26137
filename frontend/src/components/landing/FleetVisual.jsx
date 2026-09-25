import React from 'react';
import { Truck, Route, TrendingDown, Activity, MapPin } from 'lucide-react';

// Hero centerpiece: a stylized route between three network nodes with a
// flowing dashed path (Route/Job/Depot), a floating vehicle card at the
// center, and small status chips that sell the "intelligent fleet" concept
// without wiring up any real scenario data - this is marketing surface, the
// dashboard's NetworkMap owns the actual live network rendering.
export default function FleetVisual() {
  return (
    <div
      className="relative w-full aspect-[4/3] sm:aspect-[5/4] rounded-3xl border border-[#332E29] landing-grid-bg overflow-hidden shadow-2xl"
      role="img"
      aria-label="Illustration of an intelligent fleet vehicle following an optimized route between network nodes, with live status indicators for route quality, congestion, and fleet activity"
    >
      {/* Ambient glow behind the vehicle */}
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="w-40 h-40 sm:w-56 sm:h-56 rounded-full bg-[#C6602E] blur-3xl landing-glow-pulse" />
      </div>

      {/* Route path + nodes */}
      <svg
        className="absolute inset-0 w-full h-full"
        viewBox="0 0 400 320"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <path
          d="M 50 250 C 120 150, 160 110, 200 160 S 300 230, 350 70"
          fill="none"
          stroke="#3A342E"
          strokeWidth="3"
        />
        <path
          d="M 50 250 C 120 150, 160 110, 200 160 S 300 230, 350 70"
          fill="none"
          stroke="#E8A93A"
          strokeWidth="3"
          strokeLinecap="round"
          className="landing-route-flow"
        />
        <circle cx="50" cy="250" r="6" fill="#171513" stroke="#C6602E" strokeWidth="2" />
        <circle cx="200" cy="160" r="5" fill="#C6602E" className="landing-node-pulse" />
        <circle cx="350" cy="70" r="6" fill="#171513" stroke="#6B9A57" strokeWidth="2" />
      </svg>

      {/* Depot / destination markers */}
      <div className="absolute left-[9%] bottom-[18%] flex items-center gap-1 text-[10px] font-mono text-gray-400">
        <MapPin className="w-3 h-3 text-[#C6602E]" />
        Depot
      </div>
      <div className="absolute right-[6%] top-[16%] flex items-center gap-1 text-[10px] font-mono text-gray-400">
        <MapPin className="w-3 h-3 text-[#6B9A57]" />
        Destination
      </div>

      {/* Central vehicle card */}
      <div className="absolute inset-0 flex items-center justify-center">
        <div className="landing-float">
          <div className="group relative bg-[#1E1B18] border border-[#3A342E] rounded-2xl p-5 sm:p-6 shadow-[0_0_40px_-10px_rgba(198,96,46,0.45)] hover:shadow-[0_0_55px_-8px_rgba(198,96,46,0.65)] transition-shadow duration-300">
            <div className="bg-[#3A2318] border border-[#5A3A22] rounded-xl p-4 sm:p-5">
              <Truck className="w-9 h-9 sm:w-11 sm:h-11 text-[#E8A93A]" strokeWidth={1.75} />
            </div>
            <span className="absolute -top-2 -right-2 flex h-3.5 w-3.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#6B9A57] opacity-75" />
              <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-[#6B9A57] border border-[#0D0C0B]" />
            </span>
          </div>
        </div>
      </div>

      {/* Status chips */}
      <div
        className="absolute left-[6%] top-[10%] landing-float-chip"
        style={{ animationDelay: '0.3s' }}
      >
        <StatusChip icon={Route} label="Optimal Route" tone="accent" />
      </div>
      <div
        className="absolute right-[8%] bottom-[26%] landing-float-chip"
        style={{ animationDelay: '1s' }}
      >
        <StatusChip icon={TrendingDown} label="Traffic Reduced" tone="green" />
      </div>
      <div
        className="absolute left-[10%] bottom-[8%] landing-float-chip"
        style={{ animationDelay: '1.6s' }}
      >
        <StatusChip icon={Activity} label="Fleet Active" tone="amber" pulse />
      </div>
    </div>
  );
}

function StatusChip({ icon: Icon, label, tone, pulse }) {
  const toneClasses = {
    accent: 'bg-[#3A2318] border-[#5A3A22] text-[#E8A578]',
    green: 'bg-[#22301B] border-[#3A4A2E] text-[#9FC589]',
    amber: 'bg-[#3A2E14] border-[#5A4A22] text-[#E8C588]'
  }[tone];

  const dotClasses = {
    accent: 'bg-[#C6602E]',
    green: 'bg-[#6B9A57]',
    amber: 'bg-[#E8A93A]'
  }[tone];

  return (
    <div
      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1.5 shadow-lg backdrop-blur-sm text-[10px] sm:text-[11px] font-mono font-semibold ${toneClasses}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${dotClasses} ${pulse ? 'animate-pulse' : ''}`} />
      <Icon className="w-3 h-3" strokeWidth={2.25} />
      {label}
    </div>
  );
}
