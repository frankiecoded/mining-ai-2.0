import { motion } from 'framer-motion';

interface ProgressBarProps {
  value: number; // 0..100
  tone?: 'sky' | 'amber' | 'emerald';
}

const tones = {
  sky: 'from-sky-400 to-violet-500',
  amber: 'from-amber-400 to-orange-500',
  emerald: 'from-emerald-400 to-teal-500',
} as const;

export function ProgressBar({ value, tone = 'sky' }: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className="h-1.5 w-full rounded-full bg-white/[0.07] overflow-hidden">
      <motion.div
        className={`h-full rounded-full bg-gradient-to-r ${tones[tone]}`}
        initial={{ width: 0 }}
        animate={{ width: `${clamped}%` }}
        transition={{ type: 'spring', stiffness: 120, damping: 22 }}
      />
    </div>
  );
}
