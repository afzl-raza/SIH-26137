import React from 'react';
import { Route as RouteIcon, ArrowRight, SlidersHorizontal } from 'lucide-react';
import NetworkMap from '../NetworkMap';
import Button from '../ui/Button';
import SectionHeader from './SectionHeader';
import { CORE_METRICS, fmt, pctChange, stopsServed } from './metrics';

const COMPARED = CORE_METRICS.filter(m => m.key !== 'runtime');

// Two real, read-only maps side by side - actual map tiles, depot, stops,
// vehicle markers and routes - for whichever before/after pair
// pickComparison() chose, followed directly by the measured difference in
// plain language. Nothing here is computed differently from the Engineering
// Control Room; this is a presentation of the same real results.
export default function NetworkComparison({ scenario, scenarioId, comparison, onOpenEngineering }) {
  const { kind, before, after } = comparison;

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-4">
      <div className="space-y-1">
        <SectionHeader icon={RouteIcon} title="See the Difference" />
        <p className="text-xs text-gray-500">{comparison.source}</p>
      </div>

      <div className="grid lg:grid-cols-[1fr_auto_1fr] gap-3 items-stretch">
        <MapPane
          tone="before"
          title={comparison.beforeTitle}
          subtitle={comparison.beforeSubtitle}
          scenario={scenario}
          scenarioId={scenarioId}
          result={before}
        />
        <div className="hidden lg:flex items-center justify-center text-[#C6602E]">
          <ArrowRight size={22} />
        </div>
        <MapPane
          tone="after"
          title={comparison.afterTitle}
          subtitle={comparison.afterSubtitle}
          scenario={scenario}
          scenarioId={scenarioId}
          result={after}
        />
      </div>

      {kind === 'none'
        ? <NoBaselineHint onOpenEngineering={onOpenEngineering} />
        : <ComparisonStrip before={before} after={after} scenario={scenario} />}
    </div>
  );
}

function MapPane({ tone, title, subtitle, scenario, scenarioId, result }) {
  const isAfter = tone === 'after';
  const routeCount = result?.routes?.length ?? 0;
  return (
    <div className={`rounded-xl border overflow-hidden flex flex-col ${isAfter ? 'border-[#5A3A22]' : 'border-[#332E29]'}`}>
      <div className={`px-3 py-2 flex items-start justify-between gap-2 ${isAfter ? 'bg-[#3A2318]/40' : 'bg-[#141210]/60'}`}>
        <div className="min-w-0">
          <div className={`text-[11px] font-bold uppercase tracking-wider ${isAfter ? 'text-[#E8A578]' : 'text-gray-300'}`}>
            {title}
          </div>
          <div className="text-[10px] text-gray-500 mt-0.5 leading-snug">{subtitle}</div>
        </div>
        {result && (
          <span className="text-[10px] font-mono text-gray-400 flex-shrink-0 whitespace-nowrap">
            {routeCount} vehicle{routeCount === 1 ? '' : 's'} · {fmt(CORE_METRICS[0], result.total_travel_time)}
          </span>
        )}
      </div>
      <div className="h-[320px] sm:h-[360px]">
        <NetworkMap
          scenario={scenario}
          scenarioId={scenarioId}
          loading={false}
          currentResult={result}
          previousResult={null}
          disruptDisabled
          previewResult={null}
          previewedAlgorithm={null}
          compact
        />
      </div>
    </div>
  );
}

function ComparisonStrip({ before, after, scenario }) {
  const beforeStops = stopsServed(before, scenario);
  const afterStops = stopsServed(after, scenario);

  const cards = COMPARED.map(m => {
    const b = m.get(before);
    const a = m.get(after);
    return { key: m.key, label: m.label, from: fmt(m, b), to: fmt(m, a), pct: pctChange(b, a) };
  });

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {cards.map(c => <DeltaCard key={c.key} label={c.label} from={c.from} to={c.to} pct={c.pct} />)}
        <div className="bg-[#141210]/50 border border-[#332E29]/70 rounded-lg p-3">
          <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">Stops Served</div>
          <div className="font-display text-xl font-bold text-white mt-1 tabular-nums">
            {afterStops.served ?? '—'} / {afterStops.total ?? '—'}
          </div>
          <div className="text-[10px] font-mono text-gray-500 mt-0.5">
            before: {beforeStops.served ?? '—'} / {beforeStops.total ?? '—'}
          </div>
        </div>
      </div>
      <PlainSummary cards={cards} afterStops={afterStops} />
    </div>
  );
}

function DeltaCard({ label, from, to, pct }) {
  const better = pct != null && pct > 0;
  const same = pct != null && Math.abs(pct) < 0.05;
  const color = pct == null || same ? 'text-gray-300' : better ? 'text-[#6B9A57]' : 'text-[#E8A93A]';
  return (
    <div className="bg-[#141210]/50 border border-[#332E29]/70 rounded-lg p-3">
      <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold">{label}</div>
      <div className={`font-display text-xl font-bold mt-1 tabular-nums ${color}`}>
        {pct == null ? '—' : same ? 'No change' : `${Math.abs(pct).toFixed(1)}% ${better ? 'less' : 'more'}`}
      </div>
      <div className="text-[10px] font-mono text-gray-500 mt-0.5">{from} → {to}</div>
    </div>
  );
}

// One plain sentence built only from the real deltas above - worse results
// are stated as worse, never softened or dropped.
function PlainSummary({ cards, afterStops }) {
  const parts = cards
    .filter(c => c.pct != null && Math.abs(c.pct) >= 0.05)
    .map(c => `${Math.abs(c.pct).toFixed(1)}% ${c.pct > 0 ? 'less' : 'more'} ${c.label.toLowerCase()}`);
  if (parts.length === 0) return null;
  const stopsText = afterStops.total == null ? ''
    : afterStops.served === afterStops.total ? `All ${afterStops.total} stops covered, with `
    : `${afterStops.served} of ${afterStops.total} stops covered, with `;
  const joined = parts.length > 1 ? `${parts.slice(0, -1).join(', ')} and ${parts[parts.length - 1]}` : parts[0];
  return (
    <p className="text-sm text-gray-300 bg-[#3A2318]/20 border border-[#5A3A22]/50 rounded-lg px-3 py-2">
      <span className="text-[#E8A578] font-semibold">In short: </span>
      {stopsText}{joined}.
    </p>
  );
}

function NoBaselineHint({ onOpenEngineering }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#141210]/50 border border-dashed border-[#332E29] rounded-lg px-4 py-3">
      <p className="text-xs text-gray-400">
        Want to see how much better this plan is? Run a benchmark in the Engineering Control Room
        to compare it against simple nearest-stop dispatch on the same scenario.
      </p>
      <Button variant="secondary" size="sm" fullWidth={false} icon={SlidersHorizontal} onClick={onOpenEngineering}>
        Open Engineering Control Room
      </Button>
    </div>
  );
}
