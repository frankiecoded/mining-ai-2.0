import type { ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';

type Side = 'left' | 'right' | 'bottom';

interface SheetProps {
  open: boolean;
  onClose: () => void;
  side?: Side;
  width?: string;
  children: ReactNode;
}

/**
 * Drawer/sheet with iOS drawer easing (--ease-drawer), symmetric enter/exit
 * paths, and a drag-handle affordance on bottom sheets. Materialized (slides +
 * fades together) rather than a plain fade, per Apple's material guidance.
 */
const sideAnimations = {
  left: { initial: { x: '-100%' }, animate: { x: 0 }, exit: { x: '-100%' } },
  right: { initial: { x: '100%' }, animate: { x: 0 }, exit: { x: '100%' } },
  bottom: { initial: { y: '100%' }, animate: { y: 0 }, exit: { y: '100%' } },
} as const;

const sideLayouts = {
  left: 'left-0 top-0 bottom-0',
  right: 'right-0 top-0 bottom-0',
  bottom: 'left-0 right-0 bottom-0 max-h-[88dvh]',
} as const;

// iOS drawer curve (Ionic) — a fast commit then a long, graceful settle.
const DRAWER_EASE = [0.32, 0.72, 0, 1] as const;

export function Sheet({ open, onClose, side = 'right', width = 'w-[340px]', children }: SheetProps) {
  const anim = sideAnimations[side];
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={anim.initial}
            animate={anim.animate}
            exit={anim.exit}
            transition={{ type: 'tween', ease: DRAWER_EASE, duration: 0.42 }}
            className={`absolute ${sideLayouts[side]} ${width} max-w-[calc(100vw-24px)] glass-strong ${
              side === 'left'
                ? 'rounded-r-con-32 sm:rounded-r-con-36 border-r-0'
                : side === 'right'
                  ? 'rounded-l-con-32 sm:rounded-l-con-36 border-l-0'
                  : 'rounded-t-con-28 sm:rounded-t-con-32 border-b-0'
            } ${side === 'bottom' ? 'pb-[env(safe-area-inset-bottom,0px)]' : ''}`}
          >
            {side === 'bottom' && (
              <div className="flex justify-center pt-2.5 pb-1 shrink-0">
                <span className="w-10 h-[5px] rounded-full bg-white/[0.18]" />
              </div>
            )}
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}