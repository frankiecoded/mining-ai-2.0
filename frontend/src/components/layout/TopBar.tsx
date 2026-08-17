import { AnimatePresence, motion } from 'framer-motion';
import { Activity, Menu, Settings } from 'lucide-react';
import { IconButton } from '../ui/IconButton';
import { StatusDot } from '../ui/StatusDot';

interface TopBarProps {
  title: string;
  online: boolean;
  onToggleNav: () => void;
  onToggleTelemetry: () => void;
  onOpenSettings: () => void;
}

export function TopBar({ title, online, onToggleNav, onToggleTelemetry, onOpenSettings }: TopBarProps) {
  return (
    <header className="h-14 shrink-0 flex items-center justify-between px-3 md:px-5 border-b border-white/[0.06] bg-white/[0.03] backdrop-blur-2xl">
      <div className="flex items-center gap-3 min-w-0">
        <IconButton label="Open navigation" className="lg:hidden" onClick={onToggleNav}>
          <Menu className="w-5 h-5" />
        </IconButton>

        <div className="flex items-center gap-2.5 min-w-0">
          <AnimatePresence mode="wait">
            <motion.span
              key={title}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18, ease: 'easeOut' }}
              className="text-[15px] font-semibold text-white tracking-tight truncate"
            >
              {title}
            </motion.span>
          </AnimatePresence>
          <span className="flex items-center gap-1.5 text-[11px] font-medium">
            <StatusDot online={online} />
            <span className={online ? 'text-emerald-300' : 'text-rose-300'}>
              {online ? 'Live' : 'Offline'}
            </span>
          </span>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        <IconButton label="System telemetry" className="xl:hidden" onClick={onToggleTelemetry}>
          <Activity className="w-5 h-5" />
        </IconButton>
        <IconButton label="Settings" onClick={onOpenSettings}>
          <Settings className="w-5 h-5" />
        </IconButton>
      </div>
    </header>
  );
}
