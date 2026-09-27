import React from 'react';
import { Atom } from 'lucide-react';

// Three conceptual "clouds" of candidate solutions, each smaller and more
// converged than the last - a stand-in for what QPSO does (explore broadly,
// then narrow toward good solutions) without any math or claim of real
// quantum hardware. Purely illustrative: dot positions are fixed, not
// computed from any real run.
const STAGES = [
  {
    label: 'Possible Routes',
    caption: 'The optimizer starts with a broad, varied population of candidate routes.',
    dots: [
      [10, 20], [30, 10], [52, 22], [74, 12], [92, 24],
      [20, 45], [46, 50], [68, 44], [86, 52],
      [14, 72], [38, 78], [60, 70], [82, 76]
    ],
    highlighted: [6]
  },
  {
    label: 'Promising Solutions',
    caption: 'Weaker candidates are dropped; the search concentrates around what works.',
    dots: [
      [30, 30], [50, 22], [68, 32],
      [40, 50], [58, 54],
      [34, 70], [56, 74]
    ],
    highlighted: [3, 4]
  },
  {
    label: 'Optimized Route',
    caption: 'The search converges on an efficient, feasible route.',
    dots: [[28, 50], [46, 46], [64, 50], [82, 46]],
    highlighted: [0, 1, 2, 3],
    connected: true
  }
];

export default function QPSOExplainer() {
  return (
    <section id="qpso" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-16 items-center">
        <div className="landing-fade-up">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-2.5 py-1 rounded-full">
            <Atom className="w-3 h-3" />
            QUANTUM-INSPIRED OPTIMIZATION
          </span>
          <h2 className="mt-5 font-display font-bold text-2xl sm:text-3xl text-gray-50">
            Search smarter, not one route at a time
          </h2>
          <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed max-w-md">
            Instead of checking route combinations one by one, Q-DFRO's Quantum
            Particle Swarm Optimizer (QPSO) explores a broad solution space at
            once and narrows in on efficient, feasible routes &mdash; conceptually
            similar to swarm-based search, made quantum-inspired by how each
            candidate solution explores around its current best guess.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 landing-fade-up" style={{ animationDelay: '0.1s' }}>
          {STAGES.map((stage, stageIdx) => (
            <div key={stage.label} className="clean-card rounded-2xl p-4 flex flex-col items-center">
              <svg viewBox="0 0 100 90" className="w-full aspect-square" aria-hidden="true">
                {stage.connected && (
                  <polyline
                    points={stage.dots.map(([x, y]) => `${x},${y}`).join(' ')}
                    fill="none"
                    stroke="#C6602E"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                )}
                {stage.dots.map(([x, y], i) => {
                  const isHighlighted = stage.highlighted.includes(i);
                  return (
                    <circle
                      key={i}
                      cx={x}
                      cy={y}
                      r={isHighlighted ? 4.5 : 3}
                      fill={isHighlighted ? '#C6602E' : '#3A342E'}
                      className={isHighlighted ? 'landing-node-pulse' : ''}
                    />
                  );
                })}
              </svg>
              <p className="mt-2 text-[11px] font-mono font-semibold text-gray-300 text-center">
                {stage.label}
              </p>
              <p className="mt-1 text-[10px] text-gray-500 text-center leading-snug">
                {stage.caption}
              </p>
              {stageIdx < STAGES.length - 1 && (
                <span className="sm:hidden text-gray-600 text-lg mt-2" aria-hidden="true">&darr;</span>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
