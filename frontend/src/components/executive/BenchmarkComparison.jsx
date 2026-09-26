import React, { useState } from 'react';
import { BarChart2, Info } from 'lucide-react';
import SegmentedControl from '../ui/SegmentedControl';
import ComparisonBars from '../ui/ComparisonBars';
import Button from '../ui/Button';
import SectionHeader from './SectionHeader';
import { CORE_METRICS, ALGO_COLORS, METRIC_DESCRIPTIONS, METHOD_LABELS, fmt } from './metrics';

const TAB_LABELS = { travel_time: 'Time', distance: 'Distance', cost: 'Cost', runtime: 'Planning' };
const METHOD_ORDER = ['greedy', 'pso', 'ga', 'qpso'];

export default function BenchmarkComparison({ benchmarkData, onOpenEngineering }) {
  const [metricKey, setMetricKey] = useState('travel_time');
  if (!benchmarkData?.results) return null;
  const metric = CORE_METRICS.find(m => m.key === metricKey);

  const series = METHOD_ORDER
    .filter(id => benchmarkData.results[id])
    .map(id => ({
      key: id,
      label: METHOD_LABELS[id],
      value: metric.get(benchmarkData.results[id]),
      color: ALGO_COLORS[id]
    }));

  // Whichever method is genuinely lowest on the selected measure - stated
  // the same way whether or not it's Q-DFRO.
  const best = series.reduce((a, b) => (typeof b.value === 'number' && (a == null || b.value < a.value) ? b : a), null);

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <div className="flex items-start justify-between flex-wrap gap-2">
        <div className="space-y-1">
          <SectionHeader icon={BarChart2} title="How the Planning Methods Compare" />
          <p className="text-xs text-gray-500 max-w-xl">
            The same delivery job, solved by four different planning methods. Shorter bars are better.
          </p>
        </div>
        <div className="w-full sm:w-72">
          <SegmentedControl
            options={CORE_METRICS.map(m => ({ id: m.key, label: TAB_LABELS[m.key] }))}
            value={metricKey}
            onChange={setMetricKey}
          />
        </div>
      </div>
      <div className="flex items-start gap-1.5 text-[10px] text-gray-500">
        <Info size={11} className="mt-0.5 flex-shrink-0" />
        <span>{METRIC_DESCRIPTIONS[metricKey]}</span>
      </div>
      <ComparisonBars series={series} format={(v) => fmt(metric, v)} />
      {best && metricKey !== 'runtime' && (
        <p className="text-xs text-gray-300">
          <span className="font-semibold text-white">{best.label}</span> gave the lowest {metric.label.toLowerCase()} on this scenario.
        </p>
      )}
      <Button variant="secondary" fullWidth={false} onClick={onOpenEngineering}>
        View full benchmark details →
      </Button>
    </div>
  );
}
