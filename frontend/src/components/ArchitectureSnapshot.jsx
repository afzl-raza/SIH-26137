import React, { useState } from 'react';
import { Boxes, ArrowRight } from 'lucide-react';

// Static, clearly-labeled documentation diagrams (not live telemetry) -
// content mirrors Engineering.md Sec.2 (current architecture) and Sec.13
// (deliberately deferred, future path). Nothing here is computed from
// runtime state.
const PROTOTYPE_STAGES = [
  'Simulation', 'Route Decoder', 'Optimizer (Greedy/PSO/GA/QPSO)',
  'Common Evaluator', 'FastAPI', 'React + Leaflet'
];

const DEPLOYMENT_STAGES = [
  'OSM/OSMnx Network', 'SUMO Traffic Sim', 'Live Traffic Feed',
  'Optimizer (same engine)', 'Persistence Layer', 'FastAPI', 'React + Leaflet'
];

export default function ArchitectureSnapshot() {
  const [view, setView] = useState('prototype');
  const stages = view === 'prototype' ? PROTOTYPE_STAGES : DEPLOYMENT_STAGES;

  return (
    <div className="clean-card p-3.5 rounded-xl border border-[#3A342E] space-y-3 shadow-lg text-gray-300">
      <div className="flex items-center justify-between border-b border-[#332E29] pb-2">
        <div className="flex items-center gap-2">
          <Boxes size={16} className="text-[#8A8C4E]" />
          <h3 className="font-display font-bold text-white text-sm">ARCHITECTURE SNAPSHOT</h3>
        </div>
        <div className="flex gap-1 text-[10px] font-mono">
          <button
            onClick={() => setView('prototype')}
            className={`px-2 py-0.5 rounded transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] ${view === 'prototype' ? 'bg-[#C6602E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'}`}
          >
            Prototype
          </button>
          <button
            onClick={() => setView('deployment')}
            className={`px-2 py-0.5 rounded transition-colors focus-visible:ring-2 focus-visible:ring-[#C6602E] ${view === 'deployment' ? 'bg-[#8A8C4E] text-white' : 'bg-[#26221D] text-gray-400 hover:text-gray-200'}`}
          >
            Deployment
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 text-[10px] font-mono">
        {stages.map((stage, idx) => (
          <React.Fragment key={stage}>
            <span className={`px-1.5 py-0.5 rounded border ${
              view === 'deployment' && idx < stages.length - 3
                ? 'bg-[#2E301B]/60 border-[#4A4C2E] text-[#B8BA7E]'
                : 'bg-[#26221D] border-[#3A342E] text-gray-300'
            }`}>
              {stage}
            </span>
            {idx < stages.length - 1 && <ArrowRight size={10} className="text-gray-600" />}
          </React.Fragment>
        ))}
      </div>

      <div className="text-[10px] text-gray-500 leading-relaxed">
        {view === 'prototype'
          ? 'This is what is actually running right now.'
          : 'The optimization engine, evaluator and API layer carry over unchanged - only the data-ingestion side (real map data, live traffic, persisted runs) needs to be added.'}
      </div>
    </div>
  );
}
