import React from 'react';
import { cx } from '../../lib/cx';

// Branded loading indicator: the white car glyph moving between a start and
// destination marker along a dashed route. Always indeterminate - there is
// no backend stage/percentage to report for either an optimize run or a
// benchmark run (both are a single synchronous API call), so this never
// shows a fake percentage or a fabricated "step N of M".
export default function VehicleLoader({ label, sublabel, className = '' }) {
  return (
    <div className={cx('flex flex-col items-center gap-2 py-1', className)}>
      <div className="relative w-full max-w-[220px] h-6">
        <div className="absolute left-0 right-0 top-1/2 flex items-center" style={{ transform: 'translateY(-50%)' }}>
          <span className="w-1.5 h-1.5 rounded-full bg-[#6B6259] flex-shrink-0" />
          <span className="flex-1 border-t-2 border-dashed border-[#3A342E] mx-1" />
          <span className="w-1.5 h-1.5 rounded-full bg-[#6B6259] flex-shrink-0" />
        </div>
        <div className="vehicle-loader-van absolute">
          <svg width="20" height="12" viewBox="0 0 20 12" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect x="1" y="5" width="14" height="4.5" rx="1.5" fill="#FFFFFF" />
            <rect x="4.5" y="1.5" width="7" height="4" rx="1" fill="#FFFFFF" />
            <circle cx="5" cy="10.2" r="1.6" fill="#FFFFFF" />
            <circle cx="13" cy="10.2" r="1.6" fill="#FFFFFF" />
          </svg>
        </div>
      </div>
      <div className="flex justify-between w-full max-w-[220px] text-[8px] uppercase tracking-wider text-gray-600 font-mono">
        <span>Start</span>
        <span>Destination</span>
      </div>
      {(label || sublabel) && (
        <div className="text-center mt-1">
          {label && <div className="text-[11px] font-semibold text-[#C6602E] uppercase tracking-wider">{label}</div>}
          {sublabel && <div className="text-[10px] text-gray-500 mt-0.5">{sublabel}</div>}
        </div>
      )}
    </div>
  );
}
