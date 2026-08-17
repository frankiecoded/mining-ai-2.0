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

export function Sheet({ open, onClose, side = 'right', width = 'w-[340px]', children }: SheetProps) {
  const anim = sideAnimations[side];
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={anim.initial}
            animate={anim.animate}
            exit={anim.exit}
            transition={{ type: 'spring', stiffness: 380, damping: 36 }}
            className={`absolute ${sideLayouts[side]} ${width} glass-strong rounded-none`}
          >
            {children}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
