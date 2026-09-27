import React from 'react';
import { Network, Atom, AlertTriangle, RefreshCw, BarChart3 } from 'lucide-react';

const STEPS = [
  {
    n: '01',
    icon: Network,
    title: 'Build Network',
    description: 'Load vehicles, stops, roads, and current traffic conditions into a single problem model.'
  },
  {
    n: '02',
    icon: Atom,
    title: 'Optimize',
    description: 'QPSO searches the solution space for efficient, feasible routes.'
  },
  {
    n: '03',
    icon: AlertTriangle,
    title: 'Detect Disruptions',
    description: 'Traffic conditions and incidents change the network in real time.'
  },
  {
    n: '04',
    icon: RefreshCw,
    title: 'Re-Optimize',
    description: 'Q-DFRO adapts routes to the new conditions in seconds.'
  },
  {
    n: '05',
    icon: BarChart3,
    title: 'Benchmark',
    description: 'Compare the result against Greedy, PSO, and GA on the same scenario.'
  }
];

// Five-step overview of the demonstration flow (see Task.md's "Primary
// Demonstration" scenario) - deliberately worded without implementation
// detail, since that lives in the platform itself, not the landing page.
export default function HowItWorks() {
  return (
    <section id="how-it-works" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="max-w-2xl mb-10 sm:mb-12 landing-fade-up">
        <h2 className="font-display font-bold text-2xl sm:text-3xl text-gray-50">
          How Q-DFRO Works
        </h2>
        <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed">
          From network data to optimized routes in five steps.
        </p>
      </div>

      <div className="relative">
        {/* Connecting rail: one continuous line behind the row of icons on
            desktop, passing through every icon's center since the 5 columns
            are equal width - simpler and more robust than a line segment
            per step. Hidden below lg, where steps stack vertically. */}
        <div
          className="hidden lg:block absolute left-[10%] right-[10%] h-px bg-[#3A342E]"
          style={{ top: '2.25rem' }}
          aria-hidden="true"
        />

        <ol className="relative grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6 lg:gap-4">
          {STEPS.map(({ n, icon: Icon, title, description }, i) => (
            <li key={n} className="flex lg:flex-col items-start lg:items-stretch gap-4 lg:gap-0 landing-fade-up" style={{ animationDelay: `${i * 0.08}s` }}>
              <div className="flex flex-col items-center lg:mb-4 flex-shrink-0">
                <div className="relative w-[4.5rem] h-[4.5rem] rounded-2xl bg-[#1E1B18] border border-[#3A342E] flex items-center justify-center">
                  <Icon className="w-6 h-6 text-[#E8A93A]" strokeWidth={1.75} />
                </div>
              </div>

              <div className="lg:text-center lg:px-2">
                <div className="text-[11px] font-mono font-semibold text-[#C6602E]">{n}</div>
                <h3 className="mt-1 font-display font-semibold text-sm sm:text-base text-gray-100">
                  {title}
                </h3>
                <p className="mt-1.5 text-xs sm:text-sm text-gray-400 leading-relaxed lg:max-w-[11rem] lg:mx-auto">
                  {description}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
