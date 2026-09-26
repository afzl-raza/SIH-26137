import React from 'react';

// Generic horizontal comparison bars - one series per row, width scaled to
// the largest value in the set. Shared by the Executive Overview's
// before/after comparison (2 series) and its benchmark comparison
// (4 series, one per algorithm) so both reuse one real implementation
// instead of two copies of the same bar-chart logic.
export default function ComparisonBars({ series, format = (v) => String(v) }) {
  const numeric = series.map(s => (typeof s.value === 'number' ? s.value : 0));
  const max = Math.max(...numeric, 0.0001);

  return (
    <div className="space-y-2.5">
      {series.map(s => {
        const hasValue = typeof s.value === 'number';
        const pct = hasValue ? Math.max(3, (s.value / max) * 100) : 0;
        return (
          <div key={s.key} className="flex items-center gap-3">
            <div className="w-20 sm:w-24 text-[11px] font-medium text-gray-300 flex-shrink-0 truncate" title={s.label}>
              {s.label}
            </div>
            <div className="flex-1 bg-[#26221D] h-2.5 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, backgroundColor: s.color || '#C6602E' }}
              />
            </div>
            <div className="w-20 text-right font-mono text-[11px] text-gray-300 tabular-nums flex-shrink-0">
              {hasValue ? format(s.value) : '—'}
            </div>
          </div>
        );
      })}
    </div>
  );
}
