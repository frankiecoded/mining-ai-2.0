import { motion } from 'framer-motion';
import { useMemo, useId } from 'react';

interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  positive?: boolean;
}

function buildPath(values: number[], width: number, height: number): string {
  if (values.length < 2) return '';
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = width / (values.length - 1);
  return values
    .map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * (height - 6) - 3;
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(' ');
}

export function Sparkline({ values, width = 120, height = 36, positive = true }: SparklineProps) {
  const gradientId = useId();
  const path = useMemo(() => buildPath(values, width, height), [values, width, height]);
  const stroke = positive ? '#34d399' : '#fb7185';
  const fill = positive ? 'rgba(52,211,153,0.16)' : 'rgba(251,113,133,0.16)';

  if (values.length < 2) {
    return <div className="flex items-center justify-center text-[10px] text-zinc-600 font-mono" style={{ width, height }}>no trend</div>;
  }

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="overflow-visible">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.28" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path
        d={`${path} L${width},${height} L0,${height} Z`}
        fill={`url(#${gradientId})`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8, ease: 'easeOut' }}
      />
      <motion.path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 1, ease: 'easeOut' }}
      />
      <circle cx={width} cy={parseFloat(path.split(' ').at(-1)?.split(',')[1] ?? '0')} r="2.5" fill={fill ? stroke : stroke} />
    </svg>
  );
}
