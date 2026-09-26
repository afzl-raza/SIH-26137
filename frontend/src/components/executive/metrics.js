// Shared metric config for the Executive Overview - one definition reused by
// the optimization-impact table, the "What Changed" list, and the benchmark
// comparison, so all three read the same real fields the same way instead
// of three separate copies of the same accessor logic.
export const CORE_METRICS = [
  { key: 'travel_time', label: 'Travel Time', unit: 'min', get: r => r?.total_travel_time, decimals: 1 },
  { key: 'distance', label: 'Distance', unit: 'km', get: r => r?.total_distance, decimals: 1 },
  { key: 'cost', label: 'Cost', unit: '', get: r => r?.total_cost, decimals: 2 },
  { key: 'runtime', label: 'Runtime', unit: 'ms', get: r => r?.runtime_ms, decimals: 0 }
];

// Route count only exists on a full optimize/re-optimize result, not on a
// benchmark algorithm's summary row - kept separate so the benchmark
// comparison never offers a metric it has no real data for.
export const RESULT_METRICS = [
  ...CORE_METRICS,
  { key: 'routes', label: 'Routes', unit: '', get: r => r?.routes?.length, decimals: 0 }
];

// Matches BenchmarkPanel.jsx's ALGORITHM_COLORS so the two views agree
// visually on what each algorithm's color means.
export const ALGO_COLORS = { greedy: '#6B9A57', pso: '#5D7A9E', ga: '#8A8C4E', qpso: '#C6602E' };

export const METRIC_DESCRIPTIONS = {
  travel_time: 'Total time required to complete the planned routes.',
  distance: 'Total distance covered by all planned routes.',
  cost: 'Estimated operating cost for the route plan.',
  runtime: 'Time taken by the system to calculate the route plan.'
};

export function fmt(metric, value) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${value.toFixed(metric.decimals)}${metric.unit ? ' ' + metric.unit : ''}`;
}

export function pctChange(before, after) {
  if (typeof before !== 'number' || typeof after !== 'number' || before === 0) return null;
  return ((before - after) / before) * 100;
}

// Real coverage count: sums each route's actual job_ids against the
// scenario's actual job list - never assumes full coverage.
export function stopsServed(result, scenario) {
  const served = result?.routes
    ? new Set(result.routes.flatMap(r => r.job_ids || [])).size
    : null;
  const total = scenario?.jobs?.length ?? null;
  return { served, total };
}

export function affectedRoadCount(scenario) {
  return scenario?.edges?.filter(e => e.traffic_factor > 1.0).length ?? 0;
}
