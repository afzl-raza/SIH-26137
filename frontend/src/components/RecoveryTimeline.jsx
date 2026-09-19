import React from 'react';
import { AlertTriangle, RefreshCw, CheckCircle2 } from 'lucide-react';

function formatMs(ms) {
  if (ms == null) return '--';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// Only two segments are shown because they're the only two this system
// actually measures: how long the operator took to trigger re-optimization
// (a real client-side elapsed time), and how long re-optimization itself
// took (the backend's own reported runtime_ms). There is no separate
// "detection" step in this simulated system to report a duration for, so
// none is fabricated.
export default function RecoveryTimeline({ timeline }) {
  if (!timeline?.incidentAt) return null;

  const toReoptimizeMs = timeline.reoptimizeClickedAt
    ? timeline.reoptimizeClickedAt - timeline.incidentAt
    : null;

  return (
    <div className="text-[10px] font-mono text-gray-400 space-y-1.5">
      <div className="text-gray-500 uppercase tracking-wider text-[9px]">Recovery Timeline</div>
      <div className="flex items-center gap-1.5">
        <div className="flex items-center gap-1 text-[#C1443B]">
          <AlertTriangle size={11} />
          <span>Incident</span>
        </div>
        <div className="flex-1 border-t border-dashed border-[#3A342E] mx-1 relative">
          {toReoptimizeMs != null && (
            <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-gray-500 whitespace-nowrap tabular-nums">
              {formatMs(toReoptimizeMs)}
            </span>
          )}
        </div>
        <div className={`flex items-center gap-1 ${timeline.reoptimizeClickedAt ? 'text-[#E8A93A]' : 'text-gray-600'}`}>
          <RefreshCw size={11} />
          <span>Re-Optimizing</span>
        </div>
        <div className="flex-1 border-t border-dashed border-[#3A342E] mx-1 relative">
          {timeline.optimizingDurationMs != null && (
            <span className="absolute -top-3.5 left-1/2 -translate-x-1/2 text-gray-500 whitespace-nowrap tabular-nums">
              {formatMs(timeline.optimizingDurationMs)}
            </span>
          )}
        </div>
        <div className={`flex items-center gap-1 ${timeline.completedAt ? 'text-[#6B9A57]' : 'text-gray-600'}`}>
          <CheckCircle2 size={11} />
          <span>Re-Routed</span>
        </div>
      </div>
      {timeline.optimizingDurationMs != null && (
        <div className="text-gray-500">
          Re-optimization measured at {formatMs(timeline.optimizingDurationMs)} (backend-reported runtime)
        </div>
      )}
    </div>
  );
}
