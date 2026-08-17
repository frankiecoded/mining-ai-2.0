import { useEffect, useRef } from 'react';
import { useInView, animate } from 'framer-motion';

interface AnimatedNumberProps {
  value: number;
  format?: (n: number) => string;
  duration?: number;
}

/** Counts up to `value` when first scrolled into view, with easing. */
export function AnimatedNumber({ value, format, duration = 0.9 }: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-20px' });

  useEffect(() => {
    if (!inView || !ref.current) return;
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => {
        if (ref.current) {
          ref.current.textContent = format ? format(v) : String(Math.round(v));
        }
      },
    });
    return () => controls.stop();
  }, [inView, value, duration, format]);

  return (
    <span ref={ref} className="tabular">
      {format ? format(0) : '0'}
    </span>
  );
}
