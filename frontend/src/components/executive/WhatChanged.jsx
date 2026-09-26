import React from 'react';
import { ListChecks } from 'lucide-react';
import SectionHeader from './SectionHeader';
import { CORE_METRICS, fmt, pctChange, stopsServed } from './metrics';

export default function WhatChanged({ currentResult, previousResult, scenario }) {
  if (!previousResult) return null;

  const routesBefore = previousResult.routes?.length;
  const routesAfter = currentResult.routes?.length;
  const routesPct = pctChange(routesBefore, routesAfter);
  const { served, total } = stopsServed(currentResult, scenario);

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <SectionHeader icon={ListChecks} title="What Changed" />
      <div className="grid sm:grid-cols-2 gap-3">
        {CORE_METRICS.slice(0, 2).map(m => {
          const before = m.get(previousResult);
          const after = m.get(currentResult);
          const pct = pctChange(before, after);
          return <ChangeCard key={m.key} label={m.label} before={fmt(m, before)} after={fmt(m, after)} pct={pct} />;
        })}
        <ChangeCard label="Routes" before={routesBefore ?? '—'} after={routesAfter ?? '—'} pct={routesPct} />
        <ChangeCard label="Stops Served" before={null} after={`${served ?? '—'} / ${total ?? '—'}`} pct={null} />
      </div>
    </div>
  );
}

function ChangeCard({ label, before, after, pct }) {
  return (
    <div className="bg-[#141210]/40 border border-[#332E29]/60 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">{label}</div>
      <div className="font-mono text-sm text-gray-200 mt-0.5">
        {before != null ? `${before} → ${after}` : after}
      </div>
      {pct != null && (
        <div className={`text-xs font-semibold mt-0.5 ${pct >= 0 ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
          {pct >= 0 ? '↓' : '↑'} {Math.abs(pct).toFixed(1)}%
        </div>
      )}
    </div>
  );
}
