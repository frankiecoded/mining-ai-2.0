import type { HTMLAttributes } from 'react';

interface GlassPanelProps extends HTMLAttributes<HTMLDivElement> {
  tone?: 'default' | 'strong' | 'faint';
}

const tones = {
  default: 'glass',
  strong: 'glass-strong',
  faint: 'glass-faint',
} as const;

export function GlassPanel({ tone = 'default', className = '', children, ...rest }: GlassPanelProps) {
  return (
    <div className={`${tones[tone]} rounded-2xl ${className}`} {...rest}>
      {children}
    </div>
  );
}
