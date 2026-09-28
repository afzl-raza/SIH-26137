import React, { useState, useEffect, useRef } from 'react';
import { X, ArrowLeft, ArrowRight, MousePointerClick } from 'lucide-react';

// A spotlight walkthrough of REAL elements already on the Overview page
// (found via the data-tour attributes those components render), not a
// separate fabricated demo path - it points at the same live scenario/
// metrics/map/alerts the page itself shows, and ends by handing the
// operator off to the one interaction here that's genuinely live: clicking
// a road on the map to trigger a real re-optimize.
const STEPS = [
  {
    target: '[data-tour="hero"]',
    title: 'A real run, not a mockup',
    body: "Everything on this page came from a real optimizer call made when it loaded - the same solver the Dashboard uses, not sample data.",
  },
  {
    target: '[data-tour="metrics"]',
    title: 'Plain-language results',
    body: 'Fleet size, time on the road, an efficiency score, and feasibility - all computed by the real solver, including a real comparison against naive nearest-stop dispatch.',
  },
  {
    target: '[data-tour="live-map"]',
    title: 'Try it yourself',
    body: 'Click any road on this map to simulate a traffic incident. The plan re-optimizes in real time, right here - this is the one interaction on this page that is fully live.',
    icon: MousePointerClick,
  },
  {
    target: '[data-tour="alerts"]',
    title: 'Watch this panel',
    body: "Once you disrupt a road above, the real congestion event shows up here automatically - nothing pre-written.",
  },
  {
    target: null,
    title: 'Ready to go deeper?',
    body: 'Manual route planning, live traffic simulation, and algorithm benchmarking all live in the full Dashboard workflow, one click away.',
  },
];

export default function GuidedTour({ open, onClose, onEnterDashboard }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [rect, setRect] = useState(null);
  const rafRef = useRef(null);

  useEffect(() => {
    if (open) setStepIndex(0);
  }, [open]);

  const step = STEPS[stepIndex];

  // Keeps the spotlight glued to the target element every frame while a
  // step is active, so it tracks scrolling/resizing/layout shifts without
  // needing separate scroll/resize listeners. Cheap: one
  // getBoundingClientRect() per frame, only while the tour is open.
  useEffect(() => {
    if (!open) return undefined;
    const target = step.target ? document.querySelector(step.target) : null;
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'center' });

    const sync = () => {
      const el = step.target ? document.querySelector(step.target) : null;
      setRect(el ? el.getBoundingClientRect() : null);
      rafRef.current = requestAnimationFrame(sync);
    };
    rafRef.current = requestAnimationFrame(sync);
    return () => cancelAnimationFrame(rafRef.current);
  }, [open, stepIndex, step.target]);

  if (!open) return null;

  const isFirst = stepIndex === 0;
  const isLast = stepIndex === STEPS.length - 1;
  const handleNext = () => setStepIndex(i => Math.min(STEPS.length - 1, i + 1));
  const handleBack = () => setStepIndex(i => Math.max(0, i - 1));
  const StepIcon = step.icon;

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;
  let calloutStyle;
  if (isMobile) {
    calloutStyle = { position: 'fixed', left: 16, right: 16, bottom: 16, zIndex: 2101 };
  } else if (rect) {
    const spaceBelow = window.innerHeight - rect.bottom;
    const placeBelow = spaceBelow > 220;
    calloutStyle = {
      position: 'fixed',
      left: Math.min(Math.max(16, rect.left), window.innerWidth - 356),
      width: 340,
      zIndex: 2101,
      ...(placeBelow ? { top: rect.bottom + 14 } : { bottom: window.innerHeight - rect.top + 14 })
    };
  } else {
    calloutStyle = {
      position: 'fixed', left: '50%', top: '50%', transform: 'translate(-50%, -50%)', width: 360, zIndex: 2101
    };
  }

  return (
    <div className="fixed inset-0 z-[2100]" role="dialog" aria-modal="true" aria-label="Guided tour">
      {/* Spotlight: a bright cutout around the current target via a
          box-shadow-as-mask trick (no canvas/SVG dependency). Falls back to
          a plain dimmed backdrop on the final, target-less step. */}
      {rect ? (
        <div
          className="fixed rounded-xl ring-2 ring-[#FF7A1A] transition-[left,top,width,height] duration-200 ease-out pointer-events-none"
          style={{
            left: rect.left - 6,
            top: rect.top - 6,
            width: rect.width + 12,
            height: rect.height + 12,
            boxShadow: '0 0 0 9999px rgba(10,9,8,0.78)'
          }}
        />
      ) : (
        <div className="fixed inset-0 bg-[#0A0908]/78" onClick={onClose} />
      )}

      <div
        className="bg-[#211E1A] border border-[#3B342A] rounded-2xl p-5 shadow-2xl max-w-[calc(100vw-2rem)]"
        style={calloutStyle}
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#F5B942]">
            Step {stepIndex + 1} of {STEPS.length}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close tour"
            className="text-[#817970] hover:text-[#FFF9F1] transition-colors -m-1 p-1"
          >
            <X size={16} />
          </button>
        </div>

        <div className="flex items-start gap-2 mb-1.5">
          {StepIcon && <StepIcon size={16} className="text-[#FF7A1A] flex-shrink-0 mt-0.5" />}
          <h3 className="font-display font-bold text-[16px] text-[#FFF9F1]">{step.title}</h3>
        </div>
        <p className="text-[13px] text-[#B9B0A5] leading-relaxed mb-4">{step.body}</p>

        <div className="flex items-center justify-between gap-2">
          <button type="button" onClick={onClose} className="text-[12px] text-[#817970] hover:text-[#FFF9F1] transition-colors">
            Skip tour
          </button>
          <div className="flex items-center gap-2">
            {!isFirst && (
              <button
                type="button"
                onClick={handleBack}
                className="flex items-center gap-1 text-[12px] text-[#B9B0A5] hover:text-[#FFF9F1] px-3 py-1.5 rounded-lg transition-colors"
              >
                <ArrowLeft size={13} /> Back
              </button>
            )}
            {isLast ? (
              <button
                type="button"
                onClick={() => { onClose(); onEnterDashboard?.(); }}
                className="flex items-center gap-1.5 bg-[#FF7A1A] hover:bg-[#E86D10] text-[#100F0D] font-display font-bold text-[12px] px-3.5 py-2 rounded-lg transition-colors"
              >
                Open Dashboard
              </button>
            ) : (
              <button
                type="button"
                onClick={handleNext}
                className="flex items-center gap-1.5 bg-[#FF7A1A] hover:bg-[#E86D10] text-[#100F0D] font-display font-bold text-[12px] px-3.5 py-2 rounded-lg transition-colors"
              >
                Next <ArrowRight size={13} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
