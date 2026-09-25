import React from 'react';
import { Route, Radar, Atom, Network } from 'lucide-react';

const FEATURES = [
  {
    icon: Route,
    title: 'Dynamic Route Optimization',
    description: 'Assigns vehicles to jobs and sequences stops to minimize travel time, distance, and congestion together.'
  },
  {
    icon: Radar,
    title: 'Traffic-Aware Routing',
    description: 'Edge costs update with live network conditions, so a road incident immediately changes what "optimal" means.'
  },
  {
    icon: Atom,
    title: 'Quantum-Inspired Optimization',
    description: 'A Quantum Particle Swarm Optimizer explores the solution space, tracked and scored against classical baselines.'
  },
  {
    icon: Network,
    title: 'Fleet Intelligence',
    description: 'Re-optimizes an entire fleet in seconds when conditions shift, keeping every vehicle on a feasible, low-cost route.'
  }
];

export default function FeatureCards() {
  return (
    <section id="technology" className="max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="max-w-2xl mb-10 sm:mb-12">
        <h2 className="font-display font-bold text-2xl sm:text-3xl text-gray-50">
          Built on a real optimization engine
        </h2>
        <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed">
          Every capability below runs against the same problem model and objective
          function shown live in the platform &mdash; nothing here is a mockup.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
