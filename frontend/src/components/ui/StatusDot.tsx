interface StatusDotProps {
  online: boolean;
  className?: string;
}

export function StatusDot({ online, className = '' }: StatusDotProps) {
  return (
    <span
      className={`pulse-dot ${online ? 'text-emerald-400 bg-emerald-400' : 'text-rose-400 bg-rose-400'} ${className}`}
      aria-hidden
    />
  );
}
