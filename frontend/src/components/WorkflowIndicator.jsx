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
    <div className="clean-panel bg-[#171513] border-b border-[#332E29] px-4 sm:px-6 py-2.5 w-full">
      <div className="flex flex-col sm:flex-row items-stretch sm:items-start justify-center gap-1.5 sm:gap-0 max-w-4xl mx-auto">
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
                className={`workflow-stage workflow-stage--${stepState} relative flex-1 sm:flex-none sm:w-[152px] flex flex-row sm:flex-col items-center gap-2 sm:gap-1.5 px-2.5 sm:px-2 py-1.5 sm:py-2 rounded-md`}
              >
                <div
                  className={`workflow-stage-icon workflow-stage-icon--${stepState} flex items-center justify-center w-7 h-7 sm:w-8 sm:h-8 rounded-full shrink-0`}
                >
                  {isCompleted ? (
                    <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
                  ) : (
                    <Icon className="w-3.5 h-3.5" strokeWidth={1.85} />
                  )}
                </div>

                <div className="flex flex-col items-start sm:items-center sm:text-center min-w-0 leading-tight">
                  <span
                    className={`workflow-stage-title workflow-stage-title--${stepState} text-[11px] font-bold tracking-wide uppercase font-mono whitespace-nowrap`}
                  >
                    {index + 1} · {stage.label}
                  </span>
                  <span className="workflow-stage-desc text-[10px] leading-tight">
                    {stage.description}
                  </span>
                </div>
              </div>

              {/* Connector arrow (desktop row layout only) */}
              {index < STAGES.length - 1 && (
                <div
                  className={`workflow-arrow workflow-arrow--${arrowState} hidden sm:flex items-center justify-center shrink-0 sm:mt-[20px]`}
                >
                  <svg width="18" height="8" viewBox="0 0 18 8" fill="none">
                    <path
                      d="M1 4H15M15 4L11.5 1M15 4L11.5 7"
                      stroke="currentColor"
                      strokeWidth="1.25"
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
    </div>
  );
}
