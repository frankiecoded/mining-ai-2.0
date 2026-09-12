import { motion } from 'framer-motion';
import { Sparkles, BarChart3, FolderKanban, BookOpen, Terminal } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

const SUGGESTIONS: Array<{ icon: LucideIcon; label: string; hint: string; prompt: string }> = [
  { icon: BarChart3, label: 'Market prices', hint: 'Gold · Silver · Platinum', prompt: 'Give me the latest gold, silver, and platinum market prices.' },
  { icon: FolderKanban, label: 'Operations', hint: 'Live task breakdown', prompt: 'Summarise the current operations queue.' },
  { icon: BookOpen, label: 'Knowledge base', hint: 'What is documented', prompt: 'What documents are in the knowledge base?' },
  { icon: Terminal, label: 'Field report', hint: 'Write from findings', prompt: 'Help me draft a field report on this week’s site findings.' },
];

const spring = { type: 'spring', stiffness: 320, damping: 26 } as const;

export function ChatEmptyState({ userName, onPrompt }: { userName?: string; onPrompt: (prompt: string) => void }) {
  const firstName = userName?.trim().split(' ')[0];

  return (
    <div className="w-full flex flex-col items-center my-auto py-4 sm:py-8">
      {/* Brand mark — contained glow, no bleed over text */}
      <motion.div
        initial={{ scale: 0.85, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ ...spring, delay: 0.05 }}
        className="relative mb-6 sm:mb-8"
      >
        <motion.div
          className="absolute -inset-2.5 rounded-full bg-sky-500/25 blur-xl pointer-events-none"
          animate={{ scale: [1, 1.12, 1], opacity: [0.55, 0.95, 0.55] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
        />
        <div className="relative w-12 h-12 sm:w-14 sm:h-14 rounded-con-14 sm:rounded-con-16 bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_12px_32px_rgba(59,110,246,0.45)] border border-white/10">
          <Sparkles className="w-6 h-6 sm:w-7 sm:h-7 text-white" />
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0.14 }}
        className="text-center"
      >
        <h1 className="text-[28px] sm:text-[36px] font-semibold tracking-[-0.02em] leading-tight text-white mb-2.5 sm:mb-3 px-2">
          What can I help you with?
        </h1>
        <p className="text-[13px] sm:text-[15px] text-zinc-400 leading-relaxed">
          {firstName ? `Markets, ops, geology — ready for you, ${firstName}.` : 'Markets · Operations · Geology · Documents'}
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ ...spring, delay: 0.24 }}
        className="grid grid-cols-2 gap-2 sm:gap-3 w-full max-w-md mt-7 sm:mt-9"
      >
        {SUGGESTIONS.map((s, i) => (
          <motion.button
            key={s.label}
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ ...spring, delay: 0.3 + i * 0.05 }}
            whileHover={{ y: -2, scale: 1.015 }}
            whileTap={{ scale: 0.97 }}
            onClick={() => onPrompt(s.prompt)}
            className="glass-faint rounded-con-16 sm:rounded-con-20 p-3 sm:p-4 flex flex-col gap-2.5 sm:gap-3 text-left hover:border-sky-400/30 hover:bg-white/[0.06] transition-colors min-w-0"
          >
            <span className="w-9 h-9 sm:w-10 sm:h-10 rounded-con-10 sm:rounded-con-12 bg-sky-500/15 text-sky-300 flex items-center justify-center">
              <s.icon className="w-[18px] h-[18px] sm:w-5 sm:h-5" />
            </span>
            <span className="min-w-0">
              <span className="block text-[13px] sm:text-[14px] font-semibold text-zinc-100 truncate">{s.label}</span>
              <span className="block text-[11px] sm:text-[12px] text-zinc-500 truncate">{s.hint}</span>
            </span>
          </motion.button>
        ))}
      </motion.div>
    </div>
  );
}