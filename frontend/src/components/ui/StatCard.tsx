import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { AnimatedNumber } from './AnimatedNumber';

interface StatCardProps {
  icon: ReactNode;
  label: string;
  value: string;
  sub?: string;
  tone?: 'sky' | 'zinc' | 'emerald' | 'violet';
  animate?: number;
}

const iconTones: Record<string, string> = {
  sky: 'text-sky-300 bg-sky-400/10',
  emerald: 'text-emerald-300 bg-emerald-400/10',
  violet: 'text-violet-300 bg-violet-400/10',
  zinc: 'text-zinc-300 bg-white/[0.06]',
};

export function StatCard({ icon, label, value, sub, tone = 'zinc', animate }: StatCardProps) {
  return (
    <motion.div
      whileHover={{ y: -2 }}
      transition={{ type: 'spring', stiffness: 400, damping: 28 }}
      className="glass-faint rounded-2xl p-3.5 flex flex-col gap-2.5"
    >
      <div className={`w-8 h-8 rounded-xl inline-flex items-center justify-center ${iconTones[tone]}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-base font-semibold text-white tabular leading-tight truncate">
          {animate !== undefined ? <AnimatedNumber value={animate} format={() => value} /> : value}
        </div>
        <div className="text-[10px] uppercase tracking-wider text-zinc-500 mt-0.5 truncate">{label}</div>
        {sub && <div className="text-[10px] text-zinc-500 mt-0.5 font-mono">{sub}</div>}
      </div>
    </motion.div>
  );
}
