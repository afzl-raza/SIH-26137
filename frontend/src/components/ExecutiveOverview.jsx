import React, { useState, useMemo } from 'react';
import {
  MapPin, Route, Gauge, TrendingDown, TrendingUp, CheckCircle2,
  AlertTriangle, BarChart2, SlidersHorizontal, Truck, ListChecks
} from 'lucide-react';
import NetworkMap from './NetworkMap';
import VehicleInspector from './VehicleInspector';
import Logo from './Logo';
import Button from './ui/Button';
import SegmentedControl from './ui/SegmentedControl';
import ComparisonBars from './ui/ComparisonBars';

// Shared metric definitions - the SAME four metrics drive both the
// before/after "What Changed" comparison and the benchmark comparison
// below, so both reuse one bar-chart component and one formatting rule
// instead of two parallel implementations.
const METRICS = [
  { key: 'travel_time', label: 'Travel Time', unit: 'min', get: r => r?.total_travel_time, decimals: 1 },
  { key: 'distance', label: 'Distance', unit: 'km', get: r => r?.total_distance, decimals: 1 },
  { key: 'cost', label: 'Cost', unit: '', get: r => r?.total_cost, decimals: 2 },
  { key: 'runtime', label: 'Runtime', unit: 'ms', get: r => r?.runtime_ms, decimals: 0 }
];

// Matches BenchmarkPanel's per-algorithm colors so the two views agree
// visually rather than assigning algorithms different colors in each place.
const ALGO_COLORS = { greedy: '#6B9A57', pso: '#5D7A9E', ga: '#8A8C4E', qpso: '#C6602E' };

function fmt(metric, value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${value.toFixed(metric.decimals)}${metric.unit ? ' ' + metric.unit : ''}`;
}

export default function ExecutiveOverview({
  scenario,
  scenarioId,
  networkMeta,
  currentResult,
  previousResult,
  benchmarkData,
  incidentInfo,
  networkState,
  loading,
  selectedVehicle,
  selectedRoute,
  onSelectVehicle,
  selectedIncidentEdge,
  weights,
  onOpenEngineering
}) {
  const [selectedMetricKey, setSelectedMetricKey] = useState('travel_time');
  const [benchmarkMetricKey, setBenchmarkMetricKey] = useState('cost');

  const selectedMetric = METRICS.find(m => m.key === selectedMetricKey);
  const benchmarkMetric = METRICS.find(m => m.key === benchmarkMetricKey);

  const studyArea = networkMeta?.dataSource === 'openstreetmap'
    ? (networkMeta.location?.display_name || 'OpenStreetMap area')
    : 'Synthetic';
  const nodeCount = networkMeta?.nodeCount;
  const edgeCount = networkMeta?.edgeCount ?? scenario?.edges?.length;

  // Real-data-only primary outcome: a before/after % only appears when a
  // previous result actually exists (i.e. after a re-optimize). Otherwise
  // this states the real feasible-plan headline instead of fabricating a
  // baseline to compare against.
  const primaryOutcome = useMemo(() => {
    if (!currentResult) return null;
    if (previousResult) {
      const beforeVal = selectedMetric.get(previousResult);
      const afterVal = selectedMetric.get(currentResult);
      if (typeof beforeVal === 'number' && typeof afterVal === 'number' && beforeVal !== 0) {
        return { hasComparison: true, pct: ((beforeVal - afterVal) / beforeVal) * 100, metric: selectedMetric, beforeVal, afterVal };
      }
    }
    return { hasComparison: false };
  }, [currentResult, previousResult, selectedMetric]);

  if (!scenario) {
    return (
      <div className="clean-panel rounded-xl border border-[#332E29] p-10 text-center text-gray-500 text-sm">
        Loading scenario…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* SCENARIO */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Study Area" value={studyArea} icon={MapPin} truncate />
        <StatCard label="Network" value={nodeCount != null ? `${nodeCount} nodes` : '—'} sub={edgeCount != null ? `${edgeCount} road segments` : undefined} icon={Route} />
        <StatCard label="Vehicles" value={scenario.vehicles?.length ?? 0} icon={Truck} />
        <StatCard label="Stops" value={scenario.jobs?.length ?? 0} icon={MapPin} />
      </div>

      {!currentResult ? (
        <EmptyResultPanel onOpenEngineering={onOpenEngineering} />
      ) : (
        <>
          {/* PRIMARY OUTCOME */}
          <div className="clean-panel rounded-xl border border-[#332E29] p-6 text-center space-y-2">
            <div className="text-[11px] uppercase tracking-wider text-gray-500 font-semibold">Route Optimization Result</div>
            {primaryOutcome?.hasComparison ? (
              <>
                <div className={`font-display text-4xl sm:text-5xl font-bold tabular-nums flex items-center justify-center gap-2 ${primaryOutcome.pct >= 0 ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
                  {primaryOutcome.pct >= 0 ? <TrendingDown size={32} /> : <TrendingUp size={32} />}
                  {Math.abs(primaryOutcome.pct).toFixed(1)}%
                </div>
                <div className="text-sm text-gray-300 font-semibold uppercase tracking-wide">
                  {primaryOutcome.pct >= 0 ? 'Lower' : 'Higher'} {primaryOutcome.metric.label.toLowerCase()}
                </div>
                <div className="text-[11px] text-gray-500 font-mono">
                  Compared with the previous optimization run — {fmt(primaryOutcome.metric, primaryOutcome.beforeVal)} → {fmt(primaryOutcome.metric, primaryOutcome.afterVal)}
                </div>
              </>
            ) : (
              <>
                <div className="font-display text-2xl sm:text-3xl font-bold text-white flex items-center justify-center gap-2">
                  <CheckCircle2 size={26} className="text-[#6B9A57]" />
                  Feasible fleet plan
                </div>
                <div className="text-[11px] text-gray-500 font-mono">
                  {currentResult.routes?.length ?? 0} routes · {fmt(METRICS[0], currentResult.total_travel_time)} total travel time
                </div>
              </>
            )}
          </div>

          {/* KEY METRICS */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {METRICS.map(m => (
              <StatCard key={m.key} label={m.label} value={fmt(m, m.get(currentResult))} icon={Gauge} />
            ))}
          </div>

          {/* INTERACTIVE COMPARISON + WHAT CHANGED (shares one metric selection) */}
          {previousResult && (
            <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-4">
              <SectionHeader icon={BarChart2} title="What Changed" />
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  {METRICS.map(m => {
                    const before = m.get(previousResult);
                    const after = m.get(currentResult);
                    const pct = (typeof before === 'number' && typeof after === 'number' && before !== 0)
                      ? ((before - after) / before) * 100
                      : null;
                    const isActive = selectedMetricKey === m.key;
                    return (
                      <button
                        key={m.key}
                        type="button"
                        onClick={() => setSelectedMetricKey(m.key)}
                        className={`w-full text-left px-3 py-2 rounded-lg border transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C6602E] ${isActive ? 'border-[#C6602E] bg-[#3A2318]/30' : 'border-[#332E29] hover:border-[#3A342E] hover:bg-[#1E1B18]'}`}
                      >
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-gray-300 font-semibold uppercase tracking-wide">{m.label}</span>
                          {pct != null && (
                            <span className={`font-mono font-bold ${pct >= 0 ? 'text-[#6B9A57]' : 'text-[#E8A93A]'}`}>
                              {pct >= 0 ? '↓' : '↑'} {Math.abs(pct).toFixed(1)}%
                            </span>
                          )}
                        </div>
                        <div className="font-mono text-[11px] text-gray-500 mt-0.5">
                          {fmt(m, before)} → {fmt(m, after)}
                        </div>
                      </button>
                    );
                  })}
                </div>
                <div className="flex flex-col justify-center bg-[#141210]/40 border border-[#332E29]/60 rounded-lg p-3">
                  <div className="text-[10px] uppercase tracking-wider text-gray-500 font-semibold mb-2">
                    {selectedMetric.label} — Reference vs Optimized
                  </div>
                  <ComparisonBars
                    series={[
                      { key: 'before', label: 'Reference', value: selectedMetric.get(previousResult), color: '#6B6259' },
                      { key: 'after', label: 'Optimized', value: selectedMetric.get(currentResult), color: '#C6602E' }
                    ]}
                    format={(v) => fmt(selectedMetric, v)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* ROUTE MAP */}
          <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
            <SectionHeader icon={Route} title="Route Map" />
            <div className="grid lg:grid-cols-3 gap-3">
              <div className="lg:col-span-2 h-[360px] sm:h-[420px]">
                <NetworkMap
                  scenario={scenario}
                  scenarioId={scenarioId}
                  loading={loading}
                  currentResult={currentResult}
                  previousResult={previousResult}
                  selectedIncidentEdge={selectedIncidentEdge}
                  selectedVehicleId={selectedVehicle?.id}
                  onSelectVehicle={onSelectVehicle}
                  weights={weights}
                  disruptDisabled
                  previewResult={null}
                  previewedAlgorithm={null}
                />
              </div>
              <div className="h-[360px] sm:h-[420px]">
                <VehicleInspector
                  vehicle={selectedVehicle}
                  route={selectedRoute}
                  scenario={scenario}
                  onDeselect={() => onSelectVehicle?.(null, null)}
                />
              </div>
            </div>
          </div>

          {/* OPERATIONAL INSIGHTS */}
          <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-2">
            <SectionHeader icon={ListChecks} title="Operational Insights" />
            <ul className="grid sm:grid-cols-2 gap-x-6 gap-y-1.5 text-[12px] font-mono">
              <InsightRow
                ok={currentResult.is_feasible}
                text={currentResult.is_feasible ? 'Feasible route plan' : `${currentResult.constraint_violations || 0} constraint violation(s)`}
              />
              <InsightRow ok text={`${currentResult.routes?.length ?? 0} routes generated`} />
              <InsightRow ok text={`${(currentResult.total_distance ?? 0).toFixed(1)} km total route distance`} />
              <InsightRow ok text={`${(currentResult.total_travel_time ?? 0).toFixed(1)} min total travel time`} />
              <InsightRow ok text={`${scenario.jobs?.length ?? 0} delivery stops served`} />
              {incidentInfo && (
                <InsightRow warn text={`Traffic incident applied — ${incidentInfo.roadName} (×${incidentInfo.congestionFactor})`} />
              )}
              {networkState === 'RE-OPTIMIZED' && (
                <InsightRow ok text="Fleet re-optimized around the disruption" />
              )}
            </ul>
          </div>

          {/* BENCHMARK */}
          {benchmarkData?.results && (
            <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <SectionHeader icon={BarChart2} title="Algorithm Performance" />
                <div className="w-auto max-w-xs">
                  <SegmentedControl
                    options={METRICS.map(m => ({ id: m.key, label: m.label }))}
                    value={benchmarkMetricKey}
                    onChange={setBenchmarkMetricKey}
                  />
                </div>
              </div>
              <ComparisonBars
                series={['greedy', 'pso', 'ga', 'qpso']
                  .filter(id => benchmarkData.results[id])
                  .map(id => ({
                    key: id,
                    label: (benchmarkData.results[id].algorithm || id).toUpperCase(),
                    value: benchmarkMetric.get(benchmarkData.results[id]),
                    color: ALGO_COLORS[id]
                  }))}
                format={(v) => fmt(benchmarkMetric, v)}
              />
              <Button variant="secondary" fullWidth={false} onClick={onOpenEngineering}>
                View full benchmark details →
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function StatCard({ label, value, sub, icon: Icon, truncate }) {
  return (
    <div className="clean-card p-3.5 rounded-xl flex flex-col gap-1">
      <div className="flex items-center gap-1.5 text-gray-500 text-[10px] uppercase tracking-wider font-semibold">
        {Icon && <Icon size={11} />}
        {label}
      </div>
      <div className={`font-display text-lg font-bold text-white ${truncate ? 'truncate' : ''}`} title={truncate ? String(value) : undefined}>
        {value}
      </div>
      {sub && <div className="text-[10px] text-gray-500 font-mono">{sub}</div>}
    </div>
  );
}

function SectionHeader({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2 text-gray-300 font-semibold uppercase tracking-wider text-xs">
      {Icon && <Icon size={14} className="text-[#C6602E]" />}
      {title}
    </div>
  );
}

function InsightRow({ ok, warn, text }) {
  const Icon = warn ? AlertTriangle : (ok ? CheckCircle2 : AlertTriangle);
  const color = warn ? 'text-[#E8A93A]' : (ok ? 'text-[#6B9A57]' : 'text-[#C1443B]');
  return (
    <li className={`flex items-center gap-2 ${color}`}>
      <Icon size={13} className="flex-shrink-0" />
      <span className="text-gray-300">{text}</span>
    </li>
  );
}

function EmptyResultPanel({ onOpenEngineering }) {
  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-10 flex flex-col items-center justify-center gap-4 text-center">
      <Logo size={40} color="#FFFFFF" holeColor="#171513" className="opacity-30" />
      <div>
        <div className="font-display font-bold text-gray-200 text-sm uppercase tracking-wider">No Optimization Result</div>
        <p className="text-gray-500 text-xs mt-1.5 max-w-sm">
          Configure and run a scenario in the Engineering Control Room to generate the route plan.
        </p>
      </div>
      <Button variant="primary" fullWidth={false} onClick={onOpenEngineering} icon={SlidersHorizontal}>
        Open Engineering Control Room
      </Button>
    </div>
  );
}
