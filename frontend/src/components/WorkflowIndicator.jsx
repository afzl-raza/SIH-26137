import React from 'react';
import { Check, Circle } from 'lucide-react';

const STAGES = [
  { id: 'PLAN', label: 'PLAN' },
  { id: 'DISRUPT', label: 'DISRUPT' },
  { id: 'RE_OPTIMIZE', label: 'RE-OPTIMIZE' },
  { id: 'PROVE', label: 'PROVE' }
];

export default function WorkflowIndicator({ currentStage = 'INITIAL', narrativeText = '' }) {
  const getStageIndex = (stage) => {
    if (stage === 'INITIAL') return -1;
    return STAGES.findIndex(s => s.id === stage);
  };

  const currentIndex = getStageIndex(currentStage);

  return (
    <div className="clean-panel bg-[#171513] border-b border-[#332E29] px-3 sm:px-6 py-2 w-full flex flex-col items-center">
      {/* Phones: four equal columns, icon stacked over a small label, no
          connector lines - so "RE-OPTIMIZE" never wraps and "PROVE" is never
          clipped off the edge. sm and up: the original single row. */}
      <div className="grid grid-cols-4 w-full sm:flex sm:w-auto sm:items-center sm:justify-center sm:space-x-2 max-w-full">
        {STAGES.map((stage, index) => {
          const isCompleted = index < currentIndex;
          const isActive = index === currentIndex;
          const isUpcoming = index > currentIndex;

          const stepState = isCompleted ? 'completed' : isActive ? 'active' : 'upcoming';
          // The connector after this step reflects the state of the step it
          // leads INTO, not this step itself, matching the original logic.
          const connectorState = index < currentIndex - 1 ? 'completed' : index === currentIndex - 1 ? 'active' : 'upcoming';

          return (
            <React.Fragment key={stage.id}>
              {/* Step */}
              <div className="flex flex-col sm:flex-row items-center gap-1 sm:gap-0 sm:space-x-2 min-w-0">
                <div className="flex items-center justify-center w-5 h-5 flex-shrink-0">
                  {isCompleted && (
                    <Check className="w-4 h-4 text-[#6B9A57] font-bold" strokeWidth={3} />
                  )}
                  {isActive && (
                    <div className="relative flex items-center justify-center w-3 h-3">
                      <span className="absolute inline-flex w-full h-full rounded-full bg-[#C6602E] opacity-75 animate-ping"></span>
                      <span className="relative inline-flex w-2.5 h-2.5 rounded-full bg-[#C6602E]"></span>
                    </div>
                  )}
                  {isUpcoming && (
                    <Circle className="w-4 h-4 text-gray-600" strokeWidth={2} />
                  )}
                </div>

                <span className={`text-[9px] sm:text-xs font-semibold tracking-wide sm:tracking-wider uppercase whitespace-nowrap workflow-step--${stepState}`}>
                  <span className="hidden sm:inline">{index + 1} </span>{stage.label}
                </span>
              </div>

              {/* Connecting Line - desktop only; the mobile grid columns read
                  as a sequence on their own. */}
              {index < STAGES.length - 1 && (
                <div className={`hidden sm:block workflow-connector workflow-connector--${connectorState}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Narrative Text */}
      {narrativeText && (
        <div className="mt-2 text-center text-[11px] sm:text-xs text-gray-400 font-mono leading-snug">
          {narrativeText}
        </div>
      )}
    </div>
  );
}
