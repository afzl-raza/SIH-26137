import React, { useState } from 'react';
import { Route, Map, Truck, FlaskConical, BarChart3, LayoutGrid, ChevronsUpDown, Lightbulb, ChevronLeft, ChevronRight, X } from 'lucide-react';
import { useToast } from '../ui/Toast';

// Nav copy and structure pulled directly from the approved Figma frame
// ("Q-DFRO operations dashboard", node 4:3537 "Destinations"). Only
// "Overview" is a real, active view this round - the rest have nothing
// built behind them yet, but every one of their real capabilities already
// exists in the Dashboard workflow, so clicking one doesn't just say "not
// built" - it explains where the real thing lives and offers a one-click
// way there instead of a dead end.
const DESTINATIONS = [
  { id: 'overview', label: 'Overview', icon: LayoutGrid, active: true },
  { id: 'plan', label: 'Plan a route', icon: Route, note: "This dedicated view isn't built yet - the real route planner is one click away." },
  { id: 'traffic', label: 'Live traffic', icon: Map, note: "This dedicated view isn't built yet - simulate real traffic conditions from the Dashboard now." },
  { id: 'fleet', label: 'Fleet', icon: Truck, note: "Fleet management isn't built yet - vehicles are visible and selectable on the Dashboard's map today." },
  { id: 'simulations', label: 'Simulations', icon: FlaskConical, note: "This dedicated view isn't built yet - Run Benchmark on the Dashboard compares algorithms for real, right now." },
  { id: 'reports', label: 'Reports', icon: BarChart3, note: "Saved reports aren't built yet - the real evidence panels (E1-E6) are on the Dashboard after Run Benchmark." },
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

export default function OverviewSidebar({ open, onClose, onEnterDashboard }) {
  const [tipIndex, setTipIndex] = useState(0);
  const toast = useToast();
  const showPrevTip = () => setTipIndex(i => (i - 1 + OPERATOR_TIPS.length) % OPERATOR_TIPS.length);
  const showNextTip = () => setTipIndex(i => (i + 1) % OPERATOR_TIPS.length);

  const handleWorkspaceClick = () => {
    toast('Single-workspace prototype', {
      tone: 'error',
      detail: 'This demo runs as one workspace - multi-workspace switching is planned for a production build, not this round.'
    });
  };

  const handleDestinationClick = (d) => {
    toast(`${d.label} isn't built yet`, {
      tone: 'error',
      detail: d.note,
      action: onEnterDashboard ? { label: 'Open Dashboard', onClick: onEnterDashboard } : undefined
    });
  };

  return (
    <>
      {/* Backdrop - mobile/tablet only, closes the drawer on tap outside it. */}
      {open && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`w-[240px] flex-shrink-0 bg-[#100F0D] border-r border-[#3B342A] flex flex-col p-4 gap-6 font-sans
          fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out
          lg:static lg:translate-x-0 lg:z-auto
          ${open ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Brand + mobile close button */}
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-[#FF7A1A] flex items-center justify-center font-display font-bold text-[#100F0D] flex-shrink-0">
            Q
          </div>
          <div className="leading-tight flex-1 min-w-0">
            <div className="font-display font-bold text-[#FFF9F1] text-[15px]">Q-DFRO</div>
            <div className="text-[11px] text-[#817970]">Traffic intelligence</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close menu"
            className="lg:hidden p-1.5 rounded-lg text-[#B9B0A5] hover:text-[#FFF9F1] hover:bg-[#211E1A] transition-colors flex-shrink-0"
          >
            <X size={18} />
          </button>
        </div>

        {/* Workspace switcher - decorative, single-workspace prototype;
            clicking says so instead of doing nothing silently. */}
        <button
          type="button"
          onClick={handleWorkspaceClick}
          className="flex items-center gap-2 bg-[#211E1A] border border-[#3B342A] rounded-lg px-3 py-2 text-left hover:border-[#4A4238] transition-colors"
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
                onClick={d.active ? undefined : () => handleDestinationClick(d)}
                className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-[13px] transition-colors text-left ${
                  d.active
                    ? 'bg-[#FF7A1A]/15 text-[#FFF9F1] font-semibold cursor-default'
                    : 'text-[#817970] hover:text-[#B9B0A5] hover:bg-[#211E1A]'
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
    </>
  );
}
