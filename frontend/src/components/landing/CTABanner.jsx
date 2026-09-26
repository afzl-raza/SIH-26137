import React from 'react';
import { ArrowRight, GitBranch } from 'lucide-react';

export default function CTABanner({ onEnterApp }) {
  return (
    <section id="platform" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 pb-16 sm:pb-24">
      <div className="relative overflow-hidden rounded-3xl border border-[#332E29] bg-[#171513] px-6 sm:px-12 py-12 sm:py-16 text-center">
        <div className="absolute inset-0 landing-grid-bg opacity-60 pointer-events-none" aria-hidden="true" />
        <div className="relative">
          <span className="inline-flex items-center gap-1.5 text-[11px] font-mono font-semibold bg-[#22301B] text-[#9FC589] border border-[#3A4A2E] px-2.5 py-1 rounded-full">
            <GitBranch className="w-3 h-3" />
            LOAD NETWORK &rarr; OPTIMIZE &rarr; DISRUPT &rarr; RE-OPTIMIZE
          </span>
          <h2 className="mt-5 font-display font-bold text-2xl sm:text-3xl text-gray-50">
            Step into the fleet operations console
          </h2>
          <p className="mt-3 text-gray-400 text-sm sm:text-base max-w-xl mx-auto leading-relaxed">
            Load a transportation network, run the optimizer, trigger a live traffic
            incident, and watch routes recover &mdash; then compare QPSO against
            classical algorithms on the same problem.
          </p>
          <button
            onClick={onEnterApp}
            className="mt-7 inline-flex items-center justify-center gap-2 bg-[#C6602E] hover:bg-[#B0552A] text-white text-sm font-semibold px-6 py-3 rounded-lg shadow-lg shadow-[#C6602E]/20 transition-colors"
          >
            Explore Platform
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </section>
  );
}
