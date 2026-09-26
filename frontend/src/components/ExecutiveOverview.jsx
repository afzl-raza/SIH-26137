import React, { useMemo } from 'react';
import { SlidersHorizontal } from 'lucide-react';
import ExecutiveOutcome from './executive/ExecutiveOutcome';
import KeyMetrics from './executive/KeyMetrics';
import NetworkComparison from './executive/NetworkComparison';
import OperationalResult from './executive/OperationalResult';
import BenchmarkComparison from './executive/BenchmarkComparison';
import ScenarioDetails from './executive/ScenarioDetails';
import { pickComparison } from './executive/comparison';
import Logo from './Logo';
import Button from './ui/Button';

// The Executive Overview answers one question: what did the optimizer
// actually accomplish? Every section is driven by ONE real before/after
// pair (see pickComparison), so the headline, KPI tiles, maps and
// comparison strip can never contradict each other. Nothing here is
// fabricated; when no real "before" exists, the comparison simply says so.
//
// No live/interactive operations here - that's the Engineering Control
// Room's job. This page stays a read-only summary.
export default function ExecutiveOverview({
  scenario,
  scenarioId,
  networkMeta,
  currentResult,
  previousResult,
  benchmarkData,
  benchmarkStale,
  networkState,
  trafficMode,
  weatherEnabled,
  onOpenEngineering
}) {
  const comparison = useMemo(
    () => pickComparison({ benchmarkData, benchmarkStale, previousResult, currentResult }),
    [benchmarkData, benchmarkStale, previousResult, currentResult]
  );

  if (!scenario) {
    return (
      <div className="clean-panel rounded-xl border border-[#332E29] p-10 text-center text-gray-500 text-sm">
        Loading scenario…
      </div>
    );
  }

  if (!currentResult) {
    return (
      <div className="space-y-4">
        <EmptyResultPanel onOpenEngineering={onOpenEngineering} />
        <ScenarioDetails scenario={scenario} networkMeta={networkMeta} trafficMode={trafficMode} weatherEnabled={weatherEnabled} />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <WhatItDoes />
      <ExecutiveOutcome comparison={comparison} />
      <KeyMetrics currentResult={comparison.after} />
      <NetworkComparison
        scenario={scenario}
        scenarioId={scenarioId}
        comparison={comparison}
        onOpenEngineering={onOpenEngineering}
      />
      <OperationalResult currentResult={comparison.after} scenario={scenario} networkState={networkState} />
      <BenchmarkComparison benchmarkData={benchmarkStale ? null : benchmarkData} onOpenEngineering={onOpenEngineering} />
      <ScenarioDetails scenario={scenario} networkMeta={networkMeta} trafficMode={trafficMode} weatherEnabled={weatherEnabled} />
    </div>
  );
}

// Plain-language framing for a first-time viewer - what the system does,
// in three short steps, before any numbers.
function WhatItDoes() {
  const steps = [
    { n: 1, title: 'Takes the delivery job', text: 'A fleet of vehicles, a depot, and a list of stops that must all be visited.' },
    { n: 2, title: 'Plans the routes', text: 'Decides which vehicle visits which stops, and in what order, for the whole fleet at once.' },
    { n: 3, title: 'Reacts to traffic', text: 'When a road gets congested, it re-plans around the problem instead of sticking to the old route.' }
  ];
  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4">
      <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold mb-3">What Q-DFRO does</div>
      <div className="grid sm:grid-cols-3 gap-3">
        {steps.map(s => (
          <div key={s.n} className="flex gap-3">
            <span className="w-6 h-6 rounded-full bg-[#3A2318] border border-[#5A3A22] text-[#E8A578] text-xs font-bold flex items-center justify-center flex-shrink-0">
              {s.n}
            </span>
            <div>
              <div className="text-sm font-semibold text-gray-200">{s.title}</div>
              <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{s.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyResultPanel({ onOpenEngineering }) {
  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-10 flex flex-col items-center justify-center gap-4 text-center">
      <Logo size={40} color="#FFFFFF" holeColor="#171513" className="opacity-30" />
      <div>
        <div className="font-display font-bold text-gray-200 text-sm uppercase tracking-wider">No Route Plan Yet</div>
        <p className="text-gray-500 text-xs mt-1.5 max-w-sm">
          Run an optimization to see how the routes change and review the results here.
        </p>
      </div>
      <Button variant="primary" fullWidth={false} onClick={onOpenEngineering} icon={SlidersHorizontal}>
        Open Engineering Control Room
      </Button>
    </div>
  );
}
