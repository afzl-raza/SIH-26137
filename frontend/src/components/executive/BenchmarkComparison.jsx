import React, { useState } from 'react';
import { BarChart2, Info } from 'lucide-react';
import SegmentedControl from '../ui/SegmentedControl';
import ComparisonBars from '../ui/ComparisonBars';
import Button from '../ui/Button';
import SectionHeader from './SectionHeader';
import { CORE_METRICS, ALGO_COLORS, METRIC_DESCRIPTIONS, fmt } from './metrics';

export default function BenchmarkComparison({ benchmarkData, onOpenEngineering }) {
  const [metricKey, setMetricKey] = useState('cost');
  if (!benchmarkData?.results) return null;
  const metric = CORE_METRICS.find(m => m.key === metricKey);

  return (
    <div className="clean-panel rounded-xl border border-[#332E29] p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <SectionHeader icon={BarChart2} title="Route Plan Comparison" />
        <div className="w-full sm:w-auto sm:max-w-xs">
          <SegmentedControl
            options={CORE_METRICS.map(m => ({ id: m.key, label: m.label }))}
            value={metricKey}
            onChange={setMetricKey}
          />
        </div>
      </div>
      <div className="flex items-start gap-1.5 text-[10px] text-gray-500">
        <Info size={11} className="mt-0.5 flex-shrink-0" />
        <span>{METRIC_DESCRIPTIONS[metricKey]}</span>
      </div>
      <ComparisonBars
        series={['greedy', 'pso', 'ga', 'qpso']
          .filter(id => benchmarkData.results[id])
          .map(id => ({
            key: id,
            label: (benchmarkData.results[id].algorithm || id).toUpperCase(),
            value: metric.get(benchmarkData.results[id]),
            color: ALGO_COLORS[id]
          }))}
        format={(v) => fmt(metric, v)}
      />
      <Button variant="secondary" fullWidth={false} onClick={onOpenEngineering}>
        View full benchmark details →
      </Button>
    </div>
  );
}
