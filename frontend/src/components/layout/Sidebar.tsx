import type { ComponentType } from 'react';
import { motion } from 'framer-motion';
import {
  MessageSquare,
  Map,
  Landmark,
  FolderKanban,
  Database,
  Plus,
  Settings,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { useSessions } from '../../hooks/useSessions';
import { StatusDot } from '../ui/StatusDot';
import { Skeleton } from '../ui/Skeleton';
import type { ModuleId } from '../../types';

const MODULES: Array<{ id: ModuleId; label: string; icon: ComponentType<{ className?: string }> }> = [
  { id: 'chat', label: 'Command', icon: MessageSquare },
  { id: 'intel', label: 'Mining Intel', icon: Map },
  { id: 'finance', label: 'Finance', icon: Landmark },
  { id: 'tasks', label: 'Operations', icon: FolderKanban },
  { id: 'knowledge', label: 'Knowledge', icon: Database },
];

interface SidebarProps {
  activeModule: ModuleId;
  activeSessionId: string | null;
  onSelectModule: (m: ModuleId) => void;
  onSelectSession: (id: string) => void;
  onNewSession: () => void;
  onOpenSettings: () => void;
  sessionRefreshKey?: unknown;
}

export function Sidebar({
  activeModule,
  activeSessionId,
  onSelectModule,
  onSelectSession,
  onNewSession,
  onOpenSettings,
  sessionRefreshKey,
}: SidebarProps) {
  const { sessions, loading, refresh } = useSessions(sessionRefreshKey);

  return (
    <aside className="w-72 h-full flex flex-col border-r border-white/[0.07] bg-white/[0.02] backdrop-blur-2xl">
      {/* Brand */}
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-center gap-3 mb-6">
          <motion.div
            whileHover={{ scale: 1.04 }}
            transition={{ type: 'spring', stiffness: 400, damping: 22 }}
            className="w-10 h-10 rounded-[14px] bg-gradient-to-br from-sky-500/80 to-violet-600/80 shadow-[0_8px_20px_rgba(59,110,246,0.4)] flex items-center justify-center"
          >
            <Sparkles className="w-5 h-5 text-white" />
          </motion.div>
          <div className="min-w-0">
            <h1 className="text-[15px] font-semibold text-white tracking-tight">
              AI <span className="text-gradient">OS</span>
            </h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              <StatusDot online />
              <span className="text-[11px] text-zinc-500 font-medium">Intelligence Core</span>
            </div>
          </div>
        </div>

        <button
          onClick={onNewSession}
          className="w-full btn-primary rounded-full px-4 py-2.5 text-sm font-semibold flex items-center justify-center gap-2"
        >
          <Plus className="w-4 h-4" />
          New Command
        </button>
      </div>

      {/* Module navigation */}
      <nav className="px-3 space-y-0.5">
        {MODULES.map((m) => {
          const active = activeModule === m.id;
          return (
            <button
              key={m.id}
              onClick={() => onSelectModule(m.id)}
              className={`relative w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors duration-200 ${
                active ? 'text-white' : 'text-zinc-500 hover:text-zinc-200 hover:bg-white/[0.05]'
              }`}
            >
              {active && (
                <motion.span
                  layoutId="module-active"
                  className="absolute inset-0 rounded-xl glass-faint"
                  transition={{ type: 'spring', stiffness: 400, damping: 34 }}
                />
              )}
              <m.icon className={`w-[18px] h-[18px] relative z-10 ${active ? 'text-sky-300' : ''}`} />
              <span className="relative z-10">{m.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Session history */}
      <div className="flex-1 min-h-0 flex flex-col mt-4 pt-4 border-t border-white/[0.06]">
        <div className="flex items-center justify-between px-5 pb-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
            Sessions
          </span>
          <button
            onClick={() => void refresh()}
            className="text-zinc-600 hover:text-white transition-colors"
            aria-label="Refresh sessions"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto no-scrollbar px-3 pb-3 space-y-0.5">
          {loading && sessions.length === 0 ? (
            <div className="px-2 space-y-2.5 pt-1">
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="text-xs text-zinc-600 px-2 py-3">No sessions yet. Start a command.</p>
          ) : (
            sessions.map((s) => {
              const selected = activeSessionId === s.id && activeModule === 'chat';
              return (
                <motion.button
                  key={s.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  onClick={() => {
                    onSelectModule('chat');
                    onSelectSession(s.id);
                  }}
                  className={`w-full text-left px-3 py-2.5 rounded-xl transition-colors duration-200 ${
                    selected ? 'bg-white/[0.08]' : 'hover:bg-white/[0.05]'
                  }`}
                >
                  <span className={`block text-[13px] truncate ${selected ? 'text-white font-medium' : 'text-zinc-400'}`}>
                    {s.title}
                  </span>
                  <span className="block text-[11px] text-zinc-600 font-mono mt-0.5 tabular">
                    {new Date(s.time).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </motion.button>
              );
            })
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-3 border-t border-white/[0.06]">
        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-zinc-500 hover:text-white hover:bg-white/[0.05] transition-colors"
        >
          <Settings className="w-[18px] h-[18px]" />
          Settings
        </button>
      </div>
    </aside>
  );
}
