import React from 'react';
import { Play, Square } from 'lucide-react';

// The ordered steps of the scripted demo. The labels describe what the real
// handlers are doing at that moment - nothing here is a simulated result.
export const GUIDED_DEMO_STEPS = [
  { id: 'generate', label: 'Loading a fresh road network with vehicles and stops' },
  { id: 'optimize', label: 'Planning routes for the whole fleet' },
  { id: 'incident', label: 'A road on a route just jammed' },
  { id: 'reoptimize', label: 'Re-planning around the jam' },
  { id: 'benchmark', label: 'Comparing against Greedy, PSO and GA' }
];

export default function GuidedDemoBanner({ step, onStop }) {
  const index = GUIDED_DEMO_STEPS.findIndex(s => s.id === step);
  if (index < 0) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="bg-[#2A1D12] border-b border-[#5A3A22] px-3 sm:px-6 py-2 flex items-center justify-between gap-3"
    >
      <div className="flex items-center gap-2.5 min-w-0">
        <Play size={14} className="text-[#E8A93A] flex-shrink-0" />
        <div className="min-w-0">
          <div className="text-[10px] font-mono uppercase tracking-wider text-[#E8A93A]">
            Guided demo · step {index + 1} of {GUIDED_DEMO_STEPS.length}
          </div>
          <div className="text-xs text-gray-200 truncate">{GUIDED_DEMO_STEPS[index].label}</div>
        </div>
      </div>
      <div className="hidden sm:flex items-center gap-1" aria-hidden="true">
        {GUIDED_DEMO_STEPS.map((s, i) => (
          <span
            key={s.id}
            className={`h-1.5 w-6 rounded-full ${i < index ? 'bg-[#6B9A57]' : i === index ? 'bg-[#E8A93A]' : 'bg-[#3A342E]'}`}
          />
        ))}
      </div>
      <button
        onClick={onStop}
        className="flex items-center gap-1 text-[11px] font-mono text-gray-300 border border-[#5A3A22] hover:border-[#E8A93A] rounded px-2 py-1 flex-shrink-0"
      >
        <Square size={10} /> Stop
      </button>
    </div>
  );
}
