import type { ReactNode } from 'react';

interface SectionLabelProps {
  children: ReactNode;
  className?: string;
}

export function SectionLabel({ children, className = '' }: SectionLabelProps) {
  return (
    <div className={`flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500 ${className}`}>
      <span className="w-1 h-3.5 rounded-full bg-gradient-to-b from-sky-400 to-violet-500" />
      {children}
    </div>
  );
}
