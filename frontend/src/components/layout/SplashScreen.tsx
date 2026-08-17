import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';

interface SplashScreenProps {
  ready: boolean;
}

export function SplashScreen({ ready }: SplashScreenProps) {
  const [progress, setProgress] = useState(0);

  // Drive a smooth progress fill (~1.4s), independent of the backend check.
  useEffect(() => {
    const start = performance.now();
    const duration = 1400;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      setProgress(p);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center app-aurora"
      exit={{ opacity: 0, scale: 1.04 }}
      transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="aurora-blob w-[340px] h-[340px] bg-sky-600/30" />
      <div className="aurora-blob w-[280px] h-[280px] -bottom-24 right-10 bg-violet-600/30" style={{ animationDelay: '-9s' }} />

      {/* Animated brand orb */}
      <div className="relative mb-10">
        <motion.span
          className="absolute inset-0 rounded-full bg-sky-500/20 blur-2xl"
          animate={{ scale: [1, 1.25, 1], opacity: [0.6, 1, 0.6] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
        />
        <motion.span
          className="absolute -inset-3 rounded-full border border-sky-400/25"
          animate={{ scale: [1, 1.12], opacity: [0.8, 0] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeOut' }}
        />
        <motion.span
          className="absolute -inset-6 rounded-full border border-violet-400/20"
          animate={{ scale: [1, 1.1], opacity: [0.7, 0] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeOut', delay: 0.3 }}
        />
        <motion.div
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 240, damping: 18 }}
          className="relative w-20 h-20 rounded-[26px] bg-gradient-to-br from-sky-500 via-blue-600 to-violet-600 flex items-center justify-center shadow-[0_20px_60px_rgba(59,110,246,0.55)]"
        >
          <Sparkles className="w-9 h-9 text-white" />
        </motion.div>
      </div>

      <motion.h1
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15, duration: 0.5 }}
        className="text-3xl font-semibold tracking-tight text-white"
      >
        AI <span className="text-gradient">OS</span>
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.3 }}
        className="text-[13px] text-zinc-500 font-medium mt-1.5"
      >
        {ready ? 'Intelligence Core online' : 'Initializing local intelligence cluster…'}
      </motion.p>

      {/* Progress */}
      <div className="w-52 h-1 rounded-full bg-white/[0.07] overflow-hidden mt-8">
        <motion.div
          className="h-full rounded-full bg-gradient-to-r from-sky-400 to-violet-500"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
      <div className="text-[10px] font-mono text-zinc-600 uppercase tracking-[0.2em] mt-3">
        {Math.round(progress * 100)}%
      </div>
    </motion.div>
  );
}
