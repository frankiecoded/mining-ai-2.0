import type { ReactNode } from 'react';

type Tone = 'emerald' | 'amber' | 'rose' | 'sky' | 'violet' | 'zinc';

const tones: Record<Tone, string> = {
  emerald: 'text-emerald-300 bg-emerald-400/10 border-emerald-400/20',
  amber: 'text-amber-300 bg-amber-400/10 border-amber-400/20',
  rose: 'text-rose-300 bg-rose-400/10 border-rose-400/20',
  sky: 'text-sky-300 bg-sky-400/10 border-sky-400/20',
  violet: 'text-violet-300 bg-violet-400/10 border-violet-400/20',
  zinc: 'text-zinc-300 bg-white/[0.06] border-white/10',
};

interface BadgeProps {
  tone?: Tone;
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = 'zinc', children, className = '' }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-medium border ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
