import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  children: ReactNode;
}

export function IconButton({ label, className = '', children, ...rest }: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex items-center justify-center w-9 h-9 rounded-full text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors active:scale-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/60 ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}
