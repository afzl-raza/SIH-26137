import React from 'react';
import { MapPin } from 'lucide-react';

const WORKFLOW = ['Plan routes', 'Monitor traffic', 'Optimize', 'Re-optimize', 'Analyze results'];

// A stylized, static mock of the real operations console (Dashboard.jsx's
// NetworkMap + MetricCards) - same color tokens as the live map (route
// orange, free-flow green), but drawn as fixed SVG, not a live capture, so
// it stays honest about being a preview rather than a screenshot.
export default function PlatformPreview() {
  return (
    <section id="platform" className="scroll-mt-20 max-w-6xl mx-auto px-4 sm:px-6 py-16 sm:py-20 border-t border-[#332E29]">
      <div className="max-w-2xl mb-10 sm:mb-12 landing-fade-up">
        <h2 className="font-display font-bold text-2xl sm:text-3xl text-gray-50">
          Q-DFRO Operations
        </h2>
        <p className="mt-3 text-gray-400 text-sm sm:text-base leading-relaxed">
          {WORKFLOW.join(' → ')}.
        </p>
      </div>

      <div className="clean-card rounded-2xl overflow-hidden shadow-2xl landing-fade-up" style={{ animationDelay: '0.1s' }}>
        {/* Window chrome, purely decorative */}
        <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-[#3A342E] bg-[#171513]" aria-hidden="true">
          <span className="w-2.5 h-2.5 rounded-full bg-[#3A342E]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#3A342E]" />
          <span className="w-2.5 h-2.5 rounded-full bg-[#3A342E]" />
          <span className="ml-3 text-[10px] font-mono text-gray-600">Network Map</span>
        </div>

        <div className="relative aspect-[16/9] sm:aspect-[21/9] landing-grid-bg">
          <svg viewBox="0 0 400 160" className="absolute inset-0 w-full h-full" preserveAspectRatio="none" aria-hidden="true">
            <path d="M 40 120 L 150 120 L 220 60 L 360 60" fill="none" stroke="#3A342E" strokeWidth="2.5" />
            <path d="M 40 120 L 150 120 L 220 60 L 360 60" fill="none" stroke="#C6602E" strokeWidth="2.5" strokeLinecap="round" className="landing-route-flow" />
            <path d="M 150 120 L 200 140 L 300 130" fill="none" stroke="#3A342E" strokeWidth="2.5" />
            <circle cx="40" cy="120" r="6" fill="#171513" stroke="#E8A93A" strokeWidth="2" />
            <circle cx="150" cy="120" r="5" fill="#C6602E" className="landing-node-pulse" />
            <circle cx="220" cy="60" r="5" fill="#6B9A57" />
            <circle cx="300" cy="130" r="5" fill="#6B9A57" />
            <circle cx="360" cy="60" r="6" fill="#171513" stroke="#6B9A57" strokeWidth="2" />
          </svg>
          <div className="absolute left-3 bottom-3 flex items-center gap-1 text-[10px] font-mono text-gray-500">
            <MapPin className="w-3 h-3 text-[#C6602E]" />
            3 vehicles &middot; 15 stops
          </div>
        </div>

        {/* Metric strip - same field names as the real MetricCards
            (total_cost / total_travel_time / total_distance), illustrative
            values only, never presented as a real run's result. */}
        <div className="grid grid-cols-3 divide-x divide-[#3A342E] border-t border-[#3A342E] bg-[#171513]">
          {[
            { label: 'Cost', value: '842.2' },
            { label: 'Travel Time', value: '126 min' },
            { label: 'Distance', value: '83.4 km' }
          ].map(({ label, value }) => (
            <div key={label} className="px-4 py-3 text-center">
              <div className="text-[10px] font-mono text-gray-500 uppercase tracking-wide">{label}</div>
              <div className="mt-0.5 font-display font-bold text-sm sm:text-base text-gray-100 tabular-nums">
                {value}
              </div>
            </div>
          ))}
        </div>
      </div>
      <p className="mt-2 text-[11px] text-gray-600">
        Illustrative preview &mdash; real metrics are generated from your scenario in the platform.
      </p>
    </section>
  );
}
