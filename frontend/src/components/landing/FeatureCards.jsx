import React from 'react';
import { Radar, Atom, RefreshCw, BarChart3, Eye } from 'lucide-react';

const FEATURES = [
  {
    icon: Radar,
    title: 'Traffic-Aware',
    description: 'Edge costs update with live network conditions, so a road incident immediately changes what "optimal" means.'
  },
  {
    icon: Atom,
    title: 'Quantum-Inspired',
    description: 'QPSO explores a broad solution space efficiently, instead of checking one route combination at a time.'
  },
  {
    icon: RefreshCw,
    title: 'Dynamic Re-Routing',
    description: 'Responds to disruptions in seconds by re-optimizing the whole fleet, instead of relying on a static plan.'
  },
  {
    icon: BarChart3,
    title: 'Benchmarked',
    description: 'Every run is compared against Greedy, PSO, and GA on the same scenario — not claimed against them.'
  },
  {
    icon: Eye,
    title: 'Explainable',
    description: 'See why a route was chosen: the cost breakdown and convergence behavior behind each decision.'
  }
];

export default function FeatureCards() {
  return (
    <section id="technology" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="max-w-2xl mb-10 sm:mb-12">
        <h2 className="font-display font-bold text-2xl sm:text-3xl text-gray-50">
          Why Q-DFRO
        </h2>
        <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed">
          Every capability below runs against the same problem model and objective
          function shown live in the platform &mdash; nothing here is a mockup.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {FEATURES.map(({ icon: Icon, title, description }) => (
          <div
            key={title}
            className="clean-card rounded-2xl p-5 hover:border-[#5A3A22] hover:-translate-y-1 transition-all duration-300"
          >
            <div className="bg-[#3A2318] border border-[#5A3A22] w-10 h-10 rounded-lg flex items-center justify-center mb-4">
              <Icon className="w-5 h-5 text-[#E8A93A]" strokeWidth={1.9} />
            </div>
            <h3 className="font-display font-semibold text-sm sm:text-base text-gray-100">
              {title}
            </h3>
            <p className="mt-2 text-xs sm:text-sm text-gray-400 leading-relaxed">
              {description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
