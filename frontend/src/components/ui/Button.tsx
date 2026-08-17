import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  children?: ReactNode;
}

const base =
  'inline-flex items-center justify-center gap-2 font-medium rounded-full select-none ' +
  'transition-colors duration-200 active:scale-[0.97] disabled:opacity-50 disabled:pointer-events-none ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400/60 focus-visible:ring-offset-2 focus-visible:ring-offset-black';

const variants: Record<string, string> = {
  primary: 'btn-primary',
  secondary:
    'bg-white/[0.08] border border-white/10 text-white hover:bg-white/[0.14] backdrop-blur-xl',
  ghost: 'text-zinc-300 hover:text-white hover:bg-white/[0.07]',
};

const sizes: Record<string, string> = {
  sm: 'text-xs px-3 py-1.5',
  md: 'text-sm px-5 py-2.5',
  lg: 'text-sm px-6 py-3',
};

export function Button({ variant = 'secondary', size = 'md', className = '', children, ...rest }: ButtonProps) {
  return (
    <button className={`${base} ${variants[variant]} ${sizes[size]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
