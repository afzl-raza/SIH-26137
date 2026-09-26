import React from 'react';
import VehicleLoader from './VehicleLoader';

// Friendly copy per real, in-flight operation - no algorithm names, no
// stage counters, no fake percentage. The backend runs every one of these
// as a single synchronous call with no intermediate progress to report, so
// the progress bar is always indeterminate (an animated fill, not a
// number) - it communicates "the system is working," not "60% done."
export const OPERATION_COPY = {
  generate: {
    title: 'Preparing your road network...',
    description: 'Getting the roads and locations ready for route planning.'
  },
  optimize: {
    title: 'Optimizing your routes...',
    description: 'Finding an efficient route plan for your vehicles and stops.'
  },
  reoptimize: {
    title: 'Updating your routes...',
    description: 'Adjusting the route plan to match the latest road conditions.'
  },
  incident: {
    title: 'Updating road conditions...',
    description: 'Checking how the route plan responds to the change.'
  },
  benchmark: {
    title: 'Comparing route plans...',
    description: 'Evaluating different route options to see how they perform.'
  }
};

export default function OperationOverlay({ operation }) {
  const copy = OPERATION_COPY[operation] || OPERATION_COPY.optimize;

  return (
    <div className="fixed inset-0 z-[3000] flex items-center justify-center bg-[#0D0C0B]/75 backdrop-blur-[2px] operation-overlay-fade">
      <div className="clean-panel border border-[#332E29] rounded-2xl shadow-2xl px-8 py-8 w-[92%] max-w-sm flex flex-col items-center text-center gap-4">
        <VehicleLoader />
        <div>
          <div className="font-display font-bold text-gray-100 text-base">{copy.title}</div>
          <p className="text-gray-400 text-xs mt-1.5 leading-relaxed">{copy.description}</p>
        </div>
        <div className="w-full h-1.5 bg-[#26221D] rounded-full overflow-hidden">
          <div className="h-full w-1/3 bg-[#C6602E] rounded-full operation-overlay-progress" />
        </div>
      </div>
    </div>
  );
}
