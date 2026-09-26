// Picks ONE real before/after pair for the whole Executive Overview, so the
// headline, KPI tiles, maps and comparison strip all tell the same story
// instead of each section comparing something slightly different.
//
// Preference order - every option is a genuinely computed result, never a
// fabricated baseline:
// 1. 'dispatch': the latest benchmark's Greedy nearest-stop result vs its
//    QPSO result - two methods run on the identical scenario in the same
//    run. The most meaningful "without vs with optimization" comparison
//    available. Skipped once road conditions change after that benchmark
//    (its edge costs no longer apply).
// 2. 'replan': the previous route plan vs the current one, after a
//    re-optimization around changed road conditions.
// 3. 'none': no real "before" exists yet - only the current plan.
export function pickComparison({ benchmarkData, benchmarkStale, previousResult, currentResult }) {
  const bench = benchmarkStale ? null : benchmarkData?.results;
  // QPSO + local search is the default/flagship algorithm; plain QPSO is an
  // ablation entry, used only if the flagship result is somehow absent.
  const optimized = bench?.qpso_ls || bench?.qpso;
  if (bench?.greedy && optimized) {
    return {
      kind: 'dispatch',
      before: bench.greedy,
      after: optimized,
      beforeTitle: 'Without Optimization',
      beforeSubtitle: 'Simple dispatch - each vehicle drives to the nearest unvisited stop next.',
      afterTitle: 'With Q-DFRO Optimization',
      afterSubtitle: 'Routes planned together across the whole fleet to cut total travel.',
      comparedWith: 'simple nearest-stop dispatch',
      source: 'Latest comparison run - both plans computed on the identical scenario.'
    };
  }
  if (previousResult) {
    return {
      kind: 'replan',
      before: previousResult,
      after: currentResult,
      beforeTitle: 'Previous Route Plan',
      beforeSubtitle: 'Planned before the latest road-condition change.',
      afterTitle: 'Updated Route Plan',
      afterSubtitle: 'Re-planned around the current road conditions.',
      comparedWith: 'the previous route plan',
      source: 'Current route plan compared with the one it replaced.'
    };
  }
  return {
    kind: 'none',
    before: null,
    after: currentResult,
    beforeTitle: 'No Route Plan Yet',
    beforeSubtitle: 'Delivery stops waiting to be assigned to vehicles.',
    afterTitle: 'Optimized Route Plan',
    afterSubtitle: 'Every stop assigned to a vehicle route.',
    comparedWith: null,
    source: 'Current route plan.'
  };
}
