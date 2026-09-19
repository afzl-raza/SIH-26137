import React from 'react';
import { Cpu, ArrowRight } from 'lucide-react';

const PIPELINE = [
  'Continuous Particle',
  'Permutation',
  'Vehicle Assignment',
  'Route Decoding',
  'Fitness Evaluation'
];

export default function QPSOExplainability({ config, scenario }) {
  const algorithmLabel = (config?.algorithm || 'qpso').toUpperCase();

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-3 shadow-lg text-gray-300">
      <div className="flex items-center gap-2 border-b border-[#332E29] pb-2">
        <Cpu size={16} className="text-[#C6602E]" />
        <h3 className="font-display font-bold text-white text-sm">OPTIMIZATION ENGINE</h3>
      </div>

      <div>
        <div className="text-[#C6602E] font-bold text-sm">{algorithmLabel}</div>
        <div className="text-[11px] text-gray-500">
          Quantum-inspired Particle Swarm Optimization
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="clean-panel p-2 rounded-lg border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase tracking-wider">Population</div>
          <div className="font-mono text-gray-200 text-sm tabular-nums">{config?.population_size ?? '--'}</div>
        </div>
        <div className="clean-panel p-2 rounded-lg border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase tracking-wider">Iterations</div>
          <div className="font-mono text-gray-200 text-sm tabular-nums">{config?.max_iterations ?? '--'}</div>
        </div>
        <div className="clean-panel p-2 rounded-lg border border-[#332E29]">
          <div className="text-gray-500 text-[9px] uppercase tracking-wider">Seed</div>
          <div className="font-mono text-gray-200 text-sm tabular-nums">{config?.seed ?? '--'}</div>
        </div>
      </div>

      <div>
        <div className="text-gray-500 text-[9px] uppercase tracking-wider mb-1.5">Search Pipeline</div>
        <div className="flex flex-wrap items-center gap-1 text-[10px] font-mono">
          {PIPELINE.map((step, idx) => (
            <React.Fragment key={step}>
              <span className="px-1.5 py-0.5 rounded bg-[#26221D] text-gray-300 border border-[#3A342E]">
                {step}
              </span>
              {idx < PIPELINE.length - 1 && <ArrowRight size={10} className="text-gray-600" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {scenario?.scenario_hash && (
        <div className="text-[9px] font-mono text-gray-500 border-t border-[#332E29] pt-2 flex items-center justify-between">
          <span className="uppercase tracking-wider">Run ID</span>
          <span className="text-gray-400">{scenario.scenario_hash}</span>
        </div>
      )}

      <div className="text-[10px] text-gray-500 border-t border-[#332E29] pt-2 leading-relaxed">
        This is quantum-inspired optimization implemented as a classical
        computational algorithm — we are not claiming execution on quantum
        hardware. The novelty is applying the quantum-inspired search
        mechanism to dynamic fleet routing.
      </div>
    </div>
  );
}
