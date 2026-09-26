// Shared metric config for the Executive Overview - one definition reused by
// the before/after comparison strip and the benchmark comparison, so both
// read the same real fields the same way.
export const CORE_METRICS = [
  { key: 'travel_time', label: 'Travel Time', unit: 'min', get: r => r?.total_travel_time, decimals: 1 },
  { key: 'distance', label: 'Distance', unit: 'km', get: r => r?.total_distance, decimals: 1 },
  { key: 'cost', label: 'Cost', unit: '', get: r => r?.total_cost, decimals: 2 },
  { key: 'runtime', label: 'Runtime', unit: 'ms', get: r => r?.runtime_ms, decimals: 0 }
];

import { ALGORITHM_COLORS } from '../BenchmarkPanel';

// Derived from BenchmarkPanel's single source of truth, so the two views
// can never disagree on what each algorithm's color means.
export const ALGO_COLORS = Object.fromEntries(
  Object.entries(ALGORITHM_COLORS).map(([id, c]) => [id, c.hex])
);

// Plain-language meaning of each metric. "Cost" is the optimizer's combined
// score (weighted travel time + distance + traffic delay, plus penalties for
// broken limits) - not money - so it's described as a score, lower is better.
export const METRIC_DESCRIPTIONS = {
  travel_time: 'Total driving time for all vehicles combined. Lower is better.',
  distance: 'Total kilometres driven by all vehicles combined. Lower is better.',
  cost: 'One overall score combining travel time, distance and traffic delay. Lower is better.',
  runtime: 'How long the computer took to work out the route plan.'
};

// Everyday names for the four planning methods, for the non-technical view.
export const METHOD_LABELS = {
  greedy: 'Nearest-stop',
  pso: 'Swarm search',
  ga: 'Genetic search',
  qpso: 'Quantum search',
  qpso_ls: 'Q-DFRO',
  exact: 'Best possible'
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
