import React from 'react';
import { Navigation, Users, MapPin, Zap, Check, Circle, ChevronRight } from 'lucide-react';

const STEPS = [
  { n: 1, title: 'Choose vehicles', desc: 'Pick one or more from your fleet', icon: Users },
  { n: 2, title: 'Set destinations', desc: 'Add stops in any order', icon: MapPin },
  { n: 3, title: 'Optimize', desc: 'Compare time, distance, and traffic', icon: Zap },
];

// The onboarding checklist mirrors the "2 of 4 steps complete" state shown
// in the approved design exactly - it is static decoration, not read from
// any real per-operator progress store (this prototype has no accounts).
const CHECKLIST = [
  { label: 'Add your first vehicle', done: true },
  { label: 'Confirm your operating area', done: true },
  { label: 'Plan a traffic-aware route', done: false },
  { label: 'Invite a teammate', done: false },
];

export default function OverviewGreeting({ onEnterDashboard }) {
  const doneCount = CHECKLIST.filter(c => c.done).length;
  const pct = Math.round((doneCount / CHECKLIST.length) * 100);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr,340px] gap-4">
      {/* Hero */}
      <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-6 relative overflow-hidden">
        <div className="absolute -right-16 -top-16 w-56 h-56 rounded-full bg-[#FF7A1A]/10 pointer-events-none" />
        <div className="relative flex items-start justify-between gap-4 flex-wrap">
          <div className="max-w-xl">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[#F5B942] mb-2">
              <span className="w-1.5 h-1.5 rounded-full bg-[#F5B942]" />
              GOOD MORNING, ALEX
            </div>
            <h1 className="font-display font-bold text-[28px] sm:text-[34px] text-[#FFF9F1] leading-tight mb-3">
              Move smarter, one route at a time.
            </h1>
            <p className="text-[14px] text-[#B9B0A5] leading-relaxed">
              Q-DFRO finds practical routes around live traffic, helping your vehicles arrive
              sooner while using less time and fuel.
            </p>
          </div>
          <button
            onClick={onEnterDashboard}
            className="flex items-center gap-2 bg-[#FF7A1A] hover:bg-[#E86D10] text-[#100F0D] font-display font-bold text-[13px] px-4 py-2.5 rounded-lg transition-colors flex-shrink-0"
          >
            <Navigation size={15} />
            Plan your first route
          </button>
        </div>

        <div className="relative grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
          {STEPS.map(s => (
            <button
              key={s.n}
              onClick={onEnterDashboard}
              className="flex flex-col gap-2 bg-[#171512] border border-[#3B342A] rounded-xl px-3.5 py-3 text-left hover:border-[#FF7A1A]/50 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="w-8 h-8 rounded-lg bg-[#312B24] flex items-center justify-center text-[#FF7A1A] flex-shrink-0">
                  <s.icon size={15} />
                </div>
                <ChevronRight size={14} className="text-[#817970]" />
              </div>
              <div>
                <div className="text-[12px] font-semibold text-[#FFF9F1] whitespace-nowrap">{s.n}. {s.title}</div>
                <div className="text-[10px] text-[#817970] leading-snug mt-0.5">{s.desc}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Onboarding checklist - static, matches the approved design's fixed
          2-of-4 state; not derived from any real progress tracking. */}
      <div className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5 flex flex-col">
        <div className="flex items-center justify-between mb-1">
          <h2 className="font-display font-bold text-[15px] text-[#FFF9F1]">Let's get you set up</h2>
          <div className="w-9 h-9 rounded-full border-2 border-[#43D493] flex items-center justify-center text-[10px] font-bold text-[#43D493] flex-shrink-0">
            {pct}%
          </div>
        </div>
        <p className="text-[11px] text-[#817970] mb-3">{doneCount} of {CHECKLIST.length} steps complete</p>
        <div className="h-1.5 bg-[#312B24] rounded-full overflow-hidden mb-4">
          <div className="h-full bg-[#43D493] rounded-full" style={{ width: `${pct}%` }} />
        </div>
        <div className="flex flex-col gap-2.5">
          {CHECKLIST.map(item => (
            <div key={item.label} className="flex items-center gap-2.5">
              {item.done ? (
                <span className="w-4 h-4 rounded-full bg-[#173A2D] text-[#43D493] flex items-center justify-center flex-shrink-0">
                  <Check size={11} strokeWidth={3} />
                </span>
              ) : (
                <Circle size={16} className="text-[#3B342A] flex-shrink-0" />
              )}
              <span className={`text-[12px] flex-1 ${item.done ? 'text-[#817970] line-through' : 'text-[#FFF9F1]'}`}>
                {item.label}
              </span>
              {!item.done && <ChevronRight size={14} className="text-[#817970]" />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
