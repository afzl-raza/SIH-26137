import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import ExecutiveOutcome from './executive/ExecutiveOutcome';
import OptimizationImpact from './executive/OptimizationImpact';
import NetworkComparison from './executive/NetworkComparison';
import WhatChanged from './executive/WhatChanged';
import OperationalResult from './executive/OperationalResult';
import RoutePerformance from './executive/RoutePerformance';
import BenchmarkComparison from './executive/BenchmarkComparison';
import ScenarioDetails from './executive/ScenarioDetails';
import Logo from './Logo';
import Button from './ui/Button';

// The Executive Overview answers one question: what did the optimizer
// actually accomplish? Hierarchy (top to bottom): outcome -> impact ->
// visual before/after -> what changed -> operational result -> route
// details -> benchmark -> scenario metadata. Every number here is read
// from state App.jsx already computed - nothing is fabricated, and a
// comparison section simply doesn't render when there's no real
// previous result to compare against.
export default function ExecutiveOverview({
  scenario,
  scenarioId,
  networkMeta,
  currentResult,
  previousResult,
  benchmarkData,
  networkState,
  loading,
  selectedVehicle,
  selectedRoute,
  onSelectVehicle,
  trafficMode,
  weatherEnabled,
  weights,
  onOpenEngineering
}) {
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
      <ExecutiveOutcome currentResult={currentResult} previousResult={previousResult} />
      <OptimizationImpact currentResult={currentResult} previousResult={previousResult} />
      <NetworkComparison
        scenario={scenario}
        beforeResult={previousResult}
        afterResult={currentResult}
      />
      <WhatChanged currentResult={currentResult} previousResult={previousResult} scenario={scenario} />
      <OperationalResult currentResult={currentResult} scenario={scenario} networkState={networkState} />
      <RoutePerformance
        scenario={scenario}
        scenarioId={scenarioId}
        loading={loading}
        currentResult={currentResult}
        selectedVehicle={selectedVehicle}
        selectedRoute={selectedRoute}
        onSelectVehicle={onSelectVehicle}
        weights={weights}
      />
      <BenchmarkComparison benchmarkData={benchmarkData} onOpenEngineering={onOpenEngineering} />
      <ScenarioDetails scenario={scenario} networkMeta={networkMeta} trafficMode={trafficMode} weatherEnabled={weatherEnabled} />
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
