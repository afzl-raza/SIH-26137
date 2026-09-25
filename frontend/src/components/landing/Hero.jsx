import React from 'react';
import { ArrowRight, Sparkles } from 'lucide-react';
import FleetVisual from './FleetVisual';

export default function Hero({ onEnterApp }) {
  return (
    <section className="max-w-6xl mx-auto px-4 sm:px-6 pt-14 sm:pt-20 pb-16 sm:pb-24 grid grid-cols-1 lg:grid-cols-2 gap-10 lg:gap-12 items-center">
      <div className="landing-fade-up">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold bg-[#3A2318] text-[#E8A93A] border border-[#5A3A22] px-2.5 py-1 rounded-full">
          <Sparkles className="w-3 h-3" />
          QUANTUM-INSPIRED OPTIMIZATION
        </span>

        <h1 className="mt-5 font-display font-bold text-4xl sm:text-5xl lg:text-[3.4rem] leading-[1.08] tracking-tight text-gray-50">
          Intelligent Routes.
          <br />
          Smarter Fleets.
        </h1>

        <p className="mt-5 text-base sm:text-lg text-gray-400 max-w-xl leading-relaxed">
          Q-DFRO plans and re-plans delivery fleet routes in real time, using a
          quantum-inspired particle swarm optimizer that reacts to live traffic
          and network conditions &mdash; benchmarked against classical routing
          algorithms, not just claimed against them.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row gap-3 sm:items-center">
          <button
            onClick={onEnterApp}
            className="inline-flex items-center justify-center gap-2 bg-[#C6602E] hover:bg-[#B0552A] text-white text-sm font-semibold px-5 py-3 rounded-lg shadow-lg shadow-[#C6602E]/20 transition-colors"
          >
            Get Started
            <ArrowRight className="w-4 h-4" />
          </button>
          <a
            href="#technology"
            className="inline-flex items-center justify-center gap-2 border border-[#3A342E] hover:border-[#5A5049] text-gray-200 text-sm font-semibold px-5 py-3 rounded-lg transition-colors"
          >
            See How It Works
          </a>
        </div>

        <div className="mt-9 flex items-center gap-6 text-[11px] font-mono text-gray-500">
          <span>GRAPH-BASED NETWORK MODEL</span>
          <span className="w-1 h-1 rounded-full bg-[#3A342E]" />
          <span>LIVE RE-OPTIMIZATION</span>
        </div>
      </div>

      <div className="landing-fade-up" style={{ animationDelay: '0.15s' }}>
        <FleetVisual />
      </div>
    </section>
  );
}
