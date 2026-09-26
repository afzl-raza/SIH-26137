import { useState, useEffect, useRef } from 'react';

// Animates the *display* of a real, already-known value - both the start
// and end points are real backend numbers, and the tween never presents an
// intermediate frame as a measured reading (it's purely a rendering
// transition, same principle as the route-morph animation in NetworkMap).
// Shared by MetricCards.jsx and the Executive Overview's headline/KPI
// numbers instead of each keeping its own copy.
export function useCountUp(target, duration = 600) {
  const [value, setValue] = useState(target ?? 0);
  const fromRef = useRef(target ?? 0);

  useEffect(() => {
    if (target == null) return;
    const from = fromRef.current;
    const to = target;
    if (from === to) {
      setValue(to);
      return;
    }
    const start = performance.now();
    let raf;
    const tick = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(from + (to - from) * eased);
      if (t < 1) {
        raf = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}
