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
    <div className="clean-panel bg-[#171513] border-b border-[#332E29] px-6 py-2 w-full flex flex-col items-center">
      <div className="flex items-center justify-center space-x-2 max-w-full overflow-x-auto">
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
              <div className="flex items-center space-x-2">
                <div className="flex items-center justify-center w-5 h-5">
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

                <span className={`text-xs font-semibold tracking-wider uppercase workflow-step--${stepState}`}>
                  {index + 1} {stage.label}
                </span>
              </div>

              {/* Connecting Line */}
              {index < STAGES.length - 1 && (
                <div className={`workflow-connector workflow-connector--${connectorState}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
      
      {/* Narrative Text */}
      {narrativeText && (
        <div className="mt-2 text-center text-xs text-gray-400 font-mono">
          {narrativeText}
        </div>
      )}
    </div>
  );
}
