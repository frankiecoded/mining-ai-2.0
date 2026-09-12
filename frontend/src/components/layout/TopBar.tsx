import { AnimatePresence, motion } from 'framer-motion';
import { Activity, Menu, Settings } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import { StatusDot } from '../ui/StatusDot';
import { useAuth } from '../../contexts/AuthContext';

interface TopBarProps {
  title: string;
  online: boolean;
  onToggleNav: () => void;
  onToggleTelemetry: () => void;
  onOpenSettings: () => void;
  onOpenProfile: () => void;
}

function firstLetterOf(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed[0]!.toUpperCase() : '?';
}

export function TopBar({ title, online, onToggleNav, onToggleTelemetry, onOpenSettings, onOpenProfile }: TopBarProps) {
  const { user } = useAuth();
  const displayName = user?.display_name || user?.username || 'User';
  const roleTitle = user?.role_title || 'Team Member';
  const isAdmin = user?.role === 'admin';
  const letter = firstLetterOf(displayName);

  return (
    <header className="shrink-0 flex items-center justify-between gap-2 px-2.5 sm:px-3 md:px-5 py-2 pt-safe border-b border-white/[0.06] bg-white/[0.03] backdrop-blur-2xl">
      <div className="flex items-center gap-1.5 sm:gap-3 min-w-0">
        <IconButton label="Open navigation" className="lg:hidden" onClick={onToggleNav}>
          <Menu className="w-5 h-5" />
        </IconButton>

        <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
          <AnimatePresence mode="wait">
            <motion.span
              key={title}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="text-[14px] sm:text-[15px] font-semibold text-white tracking-tight truncate"
              title={title}
            >
              {title}
            </motion.span>
          </AnimatePresence>
          <span className="flex items-center gap-1.5">
            <StatusDot online={online} />
            <span className={`hidden sm:inline text-[11px] font-medium ${online ? 'text-emerald-300' : 'text-rose-300'}`}>
              {online ? 'Live' : 'Offline'}
            </span>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <IconButton label="System telemetry" className="2xl:hidden" onClick={onToggleTelemetry}>
          <Activity className="w-5 h-5" />
        </IconButton>
        {/* Logo-style profile button */}
        <motion.button
          type="button"
          onClick={onOpenProfile}
          aria-label={`Open profile — ${displayName}`}
          whileTap={{ scale: 0.95 }}
          transition={{ type: 'spring', stiffness: 500, damping: 28 }}
          className="group flex items-center gap-2 pl-1 pr-2.5 py-1 rounded-full border border-white/[0.07] bg-white/[0.04] hover:bg-white/[0.08] hover:border-white/[0.12] transition-colors select-none"
        >
          <span className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 via-indigo-500 to-violet-600 text-[15px] font-bold text-white shadow-[0_4px_14px_rgba(59,110,246,0.4)] border border-white/10">
            {letter}
            {isAdmin && (
              <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-amber-400 border-[1.5px] border-zinc-900" />
            )}
          </span>
          <span className="hidden sm:flex flex-col leading-tight text-left">
            <span className="text-[11px] font-semibold text-white max-w-[110px] truncate">{displayName}</span>
            <span className="text-[9px] text-zinc-400 max-w-[110px] truncate">{roleTitle}</span>
          </span>
        </motion.button>

        <IconButton label="Settings" onClick={onOpenSettings}>
          <Settings className="w-5 h-5" />
        </IconButton>
      </div>
    </header>
  );
}
