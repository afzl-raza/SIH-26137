import React from 'react';
import { Network, AlertTriangle, Atom, Scale, Check } from 'lucide-react';

const STAGES = [
  {
    id: 'PLAN',
    label: 'PLAN',
    description: 'QPSO routes the whole fleet',
    Icon: Network
  },
  {
    id: 'DISRUPT',
    label: 'DISRUPT',
    description: 'An incident congests a road',
    Icon: AlertTriangle
  },
  {
    id: 'RE_OPTIMIZE',
    label: 'RE-OPTIMIZE',
    description: 'Fresh fleet routes in seconds',
    Icon: Atom
  },
  {
    id: 'PROVE',
    label: 'PROVE',
    description: 'Benchmark vs Greedy, PSO, GA',
    Icon: Scale
  }
];

export default function WorkflowIndicator({ currentStage = 'INITIAL', narrativeText = '' }) {
  const getStageIndex = (stage) => {
    if (stage === 'INITIAL') return -1;
    return STAGES.findIndex(s => s.id === stage);
  };

  const currentIndex = getStageIndex(currentStage);

  return (
    <div className="clean-panel bg-[#171513] border-b border-[#332E29] px-4 sm:px-6 py-4 w-full">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-start justify-center gap-2 sm:gap-0 max-w-5xl mx-auto">
        {STAGES.map((stage, index) => {
          const isCompleted = index < currentIndex;
          const isActive = index === currentIndex;
          const stepState = isCompleted ? 'completed' : isActive ? 'active' : 'upcoming';
          // The arrow after this stage reflects the state of the stage it
          // leads INTO, not this stage itself: the arrow immediately before
          // the active stage is highlighted, arrows between completed
          // stages are green, and the rest stay muted.
          const arrowState = index < currentIndex - 1 ? 'completed' : index === currentIndex - 1 ? 'active' : 'upcoming';
          const { Icon } = stage;

          return (
            <React.Fragment key={stage.id}>
              {/* Stage card */}
              <div
                className={`workflow-stage workflow-stage--${stepState} flex-1 sm:flex-none sm:w-[180px] flex flex-row sm:flex-col items-center gap-3 sm:gap-2 px-3 sm:px-2 py-2.5 sm:py-3 rounded-lg`}
              >
                <div
                  className={`workflow-stage-icon workflow-stage-icon--${stepState} flex items-center justify-center w-10 h-10 sm:w-12 sm:h-12 rounded-full shrink-0`}
                >
                  {isCompleted ? (
                    <Check className="w-5 h-5" strokeWidth={2.5} />
                  ) : (
                    <Icon className="w-5 h-5" strokeWidth={1.75} />
                  )}
                </div>

                <div className="flex flex-col items-start sm:items-center sm:text-center min-w-0">
                  <span
                    className={`workflow-stage-title workflow-stage-title--${stepState} text-xs font-semibold tracking-wider uppercase font-mono whitespace-nowrap`}
                  >
                    {index + 1} · {stage.label}
                  </span>
                  <span className="workflow-stage-desc text-[11px] leading-snug mt-0.5">
                    {stage.description}
                  </span>
                </div>
              </div>

              {/* Connector arrow (desktop row layout only) */}
              {index < STAGES.length - 1 && (
                <div
                  className={`workflow-arrow workflow-arrow--${arrowState} hidden sm:flex items-center justify-center shrink-0 sm:mt-4`}
                >
                  <svg width="26" height="12" viewBox="0 0 26 12" fill="none">
                    <path
                      d="M1 6H23M23 6L18 1M23 6L18 11"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Narrative Text */}
      {narrativeText && (
        <div className="mt-3 text-center text-xs text-gray-400 font-mono">
          {narrativeText}
        </div>
      )}
    </div>
  );
}
