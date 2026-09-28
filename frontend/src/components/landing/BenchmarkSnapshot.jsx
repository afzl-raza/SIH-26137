import React from 'react';
import { Scale, Info } from 'lucide-react';

// Real algorithms Q-DFRO benchmarks against (backend/optimizers/benchmark.py
// run_benchmark) and the real metrics BenchmarkPanel.jsx reports
// (backend/models.py's OptimizationResult) - the labels here are accurate,
// but the bars are deliberately all the same length. No specific
// cost/time/distance/runtime numbers are invented for this page; those only
// ever come from an actual run, shown live in the platform.
const ALGORITHMS = ['Greedy', 'PSO', 'GA', 'QPSO'];
const METRICS = ['Cost', 'Travel Time', 'Distance', 'Runtime'];

export default function BenchmarkSnapshot() {
  return (
    <section id="benchmark" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        <div className="landing-fade-up">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-2.5 py-1 rounded-full">
            <Scale className="w-3 h-3" />
            OPTIMIZATION, MEASURED
          </span>
          <h2 className="mt-5 font-display font-bold text-2xl sm:text-3xl text-gray-50">
            Evaluated, not just claimed
          </h2>
          <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed max-w-md">
            Compare route quality, travel time, distance, and runtime across
            optimization methods on the same scenario. Q-DFRO doesn&rsquo;t assume QPSO
            wins &mdash; if Greedy, PSO, or GA scores better on a given run, the
            platform shows that too.
          </p>
        </div>

        <div className="clean-card rounded-2xl p-5 sm:p-6 landing-fade-up" style={{ animationDelay: '0.1s' }}>
          <div className="flex items-center justify-between mb-1">
            <p className="text-[11px] font-mono font-semibold text-gray-300 uppercase tracking-wide">
              Algorithm Performance
            </p>
            <span className="inline-flex items-center gap-1 text-[9px] font-mono font-bold uppercase tracking-wide text-[#E8A93A] bg-[#3A2318] border border-[#5A3A22] px-2 py-0.5 rounded-full">
              <Info className="w-2.5 h-2.5" />
              Example layout
            </span>
          </div>
          <p className="text-[11px] text-gray-500 mb-4 leading-snug">
            Not real results &mdash; every bar below is drawn the same length on purpose, to show the comparison layout without a live run to measure.
          </p>

          <div className="space-y-3">
            {ALGORITHMS.map((algo) => (
              <div key={algo} className="flex items-center gap-3">
                <span className="w-12 flex-shrink-0 text-[11px] font-mono text-gray-400">{algo}</span>
                <div
                  className="flex-1 h-2 rounded-full bg-[#26221D] overflow-hidden"
                  style={{
                    backgroundImage: 'repeating-linear-gradient(-45deg, #3A342E 0px, #3A342E 5px, #2A2620 5px, #2A2620 10px)'
                  }}
                />
              </div>
            ))}
          </div>

          <div className="mt-5 pt-4 border-t border-[#3A342E] flex flex-wrap gap-x-4 gap-y-1.5">
            {METRICS.map((metric) => (
              <span key={metric} className="text-[10px] font-mono text-gray-500">
                {metric}
              </span>
            ))}
          </div>

          <p className="mt-4 text-xs text-gray-500 leading-relaxed">
            <span className="text-gray-300 font-semibold">Real numbers appear once you run a benchmark in the platform</span>
            {' '}&mdash; nothing on this landing page is a fixed or precomputed result.
          </p>
        </div>
      </div>
    </section>
  );
}
