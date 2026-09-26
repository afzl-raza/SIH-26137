import React from 'react';
import { Gauge } from 'lucide-react';
import SectionHeader from './SectionHeader';
import { RESULT_METRICS, fmt, pctChange } from './metrics';

// Real before/after values only - a row is still shown when there's no
// improvement (the brief explicitly asks not to hide an unfavorable
// result), but never a row where one side has no real value.
export default function OptimizationImpact({ currentResult, previousResult }) {
  if (!previousResult) return null;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <SectionHeader icon={Gauge} title="Optimization Impact" />
      <div className="overflow-x-auto">
        <table className="w-full text-sm text-left">
          <thead className="text-[10px] text-gray-500 uppercase border-b border-[#332E29]">
            <tr>
              <th className="py-2 pr-4 font-semibold">Metric</th>
              <th className="py-2 pr-4 font-semibold text-right">Before</th>
              <th className="py-2 pr-4 font-semibold text-right">Optimized</th>
              <th className="py-2 font-semibold text-right">Change</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#332E29]/60">
            {RESULT_METRICS.map(m => {
              const before = m.get(previousResult);
              const after = m.get(currentResult);
              const pct = pctChange(before, after);
              return (
                <tr key={m.key}>
                  <td className="py-2 pr-4 text-gray-300">{m.label}</td>
                  <td className="py-2 pr-4 text-right text-gray-400 font-mono tabular-nums">{fmt(m, before)}</td>
                  <td className="py-2 pr-4 text-right text-white font-mono tabular-nums">{fmt(m, after)}</td>
                  <td className={`py-2 text-right font-mono tabular-nums font-semibold ${pct == null ? 'text-gray-600' : pct >= 0 ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
                    {pct == null ? '—' : `${pct >= 0 ? '↓' : '↑'} ${Math.abs(pct).toFixed(1)}%`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
