import React, { useState } from 'react';
import { Route, Map, Truck, FlaskConical, BarChart3, LayoutGrid, ChevronsUpDown, Lightbulb, ChevronLeft, ChevronRight } from 'lucide-react';

// Nav copy and structure pulled directly from the approved Figma frame
// ("Q-DFRO operations dashboard", node 4:3537 "Destinations"). Only
// "Overview" is a real, active view this round - the rest are intentionally
// inert (no onClick, no href) since nothing is built behind them yet; a
// title tooltip says so rather than silently doing nothing.
const DESTINATIONS = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid, active: true },
  { id: 'plan', label: 'Plan a route', icon: Route },
  { id: 'traffic', label: 'Live traffic', icon: Map },
  { id: 'fleet', label: 'Fleet', icon: Truck },
  { id: 'simulations', label: 'Simulations', icon: FlaskConical },
  { id: 'reports', label: 'Reports', icon: BarChart3 },
];

// Static operator tips, unrelated to live traffic conditions (those are
// OverviewAlerts.jsx's job, driven by the real scenario/edges data - this
// panel never touches that). The "N of 3" counter previously had only one
// tip behind it and no way to move to the other two, so it always read
// "Tip 1 of 3" no matter what - fixed here by actually carrying all three
// tips and letting the operator step through them.
const OPERATOR_TIPS = [
  'Start with one vehicle and one destination. You can add stops after the first route is ready.',
  'Simulate a traffic incident from the Dashboard to see how re-optimization reroutes a live fleet.',
  'Compare algorithms from the Benchmark panel to see which one fits your network best.',
];

export default function OverviewSidebar() {
  const [tipIndex, setTipIndex] = useState(0);
  const showPrevTip = () => setTipIndex(i => (i - 1 + OPERATOR_TIPS.length) % OPERATOR_TIPS.length);
  const showNextTip = () => setTipIndex(i => (i + 1) % OPERATOR_TIPS.length);

  return (
    <aside className="w-[240px] flex-shrink-0 bg-[#100F0D] border-r border-[#3B342A] flex flex-col p-4 gap-6 font-sans">
      {/* Brand */}
      <div className="flex items-center gap-2.5">
        <div className="w-9 h-9 rounded-lg bg-[#FF7A1A] flex items-center justify-center font-display font-bold text-[#100F0D] flex-shrink-0">
          Q
        </div>
        <div className="leading-tight">
          <div className="font-display font-bold text-[#FFF9F1] text-[15px]">Q-DFRO</div>
          <div className="text-[11px] text-[#817970]">Traffic intelligence</div>
        </div>
      </div>

      {/* Workspace switcher - decorative, single-workspace prototype */}
      <button
        type="button"
        title="Single-workspace prototype - not a real switcher"
        className="flex items-center gap-2 bg-[#211E1A] border border-[#3B342A] rounded-lg px-3 py-2 text-left cursor-default"
      >
        <div className="w-7 h-7 rounded bg-[#312B24] flex items-center justify-center text-[#B9B0A5] flex-shrink-0">
          <LayoutGrid size={14} />
        </div>
        <div className="flex-1 min-w-0 leading-tight">
          <div className="text-[9px] text-[#817970] uppercase tracking-wider">Workspace</div>
          <div className="text-[13px] text-[#FFF9F1] truncate">Metro operations</div>
        </div>
        <ChevronsUpDown size={14} className="text-[#817970] flex-shrink-0" />
      </button>

      {/* Destinations */}
      <nav className="flex-1 flex flex-col gap-1">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#817970] px-2 mb-1">
          Operations
        </div>
        {DESTINATIONS.map(d => {
          const Icon = d.icon;
          return (
            <button
              key={d.id}
              type="button"
              disabled={!d.active}
              title={d.active ? undefined : 'Not built yet in this prototype'}
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-colors text-left ${
                d.active
                  ? 'bg-[#FF7A1A]/15 text-[#FFF9F1] font-semibold'
                  : 'text-[#817970] cursor-default'
              }`}
            >
              <Icon size={16} className={d.active ? 'text-[#FF7A1A]' : 'text-[#817970]'} />
              {d.label}
            </button>
          );
        })}
      </nav>

      {/* Operator tip */}
      <div className="bg-[#4A2916]/40 border border-[#5A3620] rounded-lg p-3 space-y-1.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-[#F5B942]">
            <Lightbulb size={12} />
            Tip {tipIndex + 1} of {OPERATOR_TIPS.length}
          </div>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={showPrevTip}
              aria-label="Previous tip"
              className="p-0.5 rounded text-[#B9B0A5] hover:text-[#F5B942] hover:bg-[#5A3620]/40 transition-colors"
            >
              <ChevronLeft size={12} />
            </button>
            <button
              type="button"
              onClick={showNextTip}
              aria-label="Next tip"
              className="p-0.5 rounded text-[#B9B0A5] hover:text-[#F5B942] hover:bg-[#5A3620]/40 transition-colors"
            >
              <ChevronRight size={12} />
            </button>
          </div>
        </div>
        <p className="text-[11px] text-[#B9B0A5] leading-snug">
          {OPERATOR_TIPS[tipIndex]}
        </p>
      </div>

      {/* System status */}
      <div className="flex items-center gap-2 text-[11px] text-[#43D493] px-1">
        <span className="w-1.5 h-1.5 rounded-full bg-[#43D493]" />
        All systems operating
      </div>
    </aside>
  );
}
