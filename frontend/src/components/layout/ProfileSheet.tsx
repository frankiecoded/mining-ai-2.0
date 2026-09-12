import { motion } from 'framer-motion';
import { Settings, LogOut, Users, Shield } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import type { ModuleId } from '../../types';

interface ProfileSheetProps {
  onClose: () => void;
  onOpenSettings: () => void;
  onSelectModule: (m: ModuleId) => void;
}

function firstLetterOf(name: string): string {
  const trimmed = name.trim();
  return trimmed ? trimmed[0]!.toUpperCase() : '?';
}

export function ProfileSheet({ onClose, onOpenSettings, onSelectModule }: ProfileSheetProps) {
  const { user, logout } = useAuth();
  if (!user) return null;

  const displayName = user.display_name || user.username || 'User';
  const roleTitle = user.role_title || 'Team Member';
  const isAdmin = user.role === 'admin';
  const letter = firstLetterOf(displayName);

  return (
    <div className="h-full flex flex-col">
      {/* Identity header */}
      <div className="px-5 pt-6 pb-5 border-b border-white/[0.06]">
        <motion.div
          initial={{ opacity: 0, scale: 0.92, y: 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ type: 'spring', stiffness: 380, damping: 26 }}
          className="flex flex-col items-center text-center gap-3"
        >
          <div className="relative">
            <div className="w-16 h-16 rounded-[22px] bg-gradient-to-br from-sky-500 via-indigo-500 to-violet-600 flex items-center justify-center shadow-[0_14px_36px_rgba(59,110,246,0.45)] border border-white/15">
              <span className="text-[28px] font-bold text-white tracking-tight leading-none">
                {letter}
              </span>
            </div>
            {isAdmin && (
              <span className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-amber-400 border-2 border-zinc-900 flex items-center justify-center">
                <Shield className="w-2.5 h-2.5 text-zinc-900" />
              </span>
            )}
          </div>

          <div>
            <div className="text-[17px] font-semibold text-white tracking-tight">{displayName}</div>
            <div className="flex items-center justify-center gap-1.5 mt-1">
              <span className="text-[12px] text-zinc-400">{roleTitle}</span>
              <span className="text-zinc-600">·</span>
              <span className={`text-[11px] font-semibold uppercase tracking-wider ${isAdmin ? 'text-amber-300/90' : 'text-sky-300/80'}`}>
                {isAdmin ? 'Admin' : 'Member'}
              </span>
            </div>
            {user.email && <div className="text-[11px] text-zinc-600 mt-1.5 font-mono">{user.email}</div>}
          </div>

          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.05] border border-white/[0.07] text-[10px] text-zinc-500">
            @{user.username}
          </span>
        </motion.div>
      </div>

      {/* Actions */}
      <div className="flex-1 px-3 py-4 space-y-1">
        {isAdmin && (
          <button
            onClick={() => onSelectModule('team')}
            className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <span className="w-9 h-9 rounded-xl bg-sky-500/10 text-sky-300 inline-flex items-center justify-center">
              <Users className="w-[18px] h-[18px]" />
            </span>
            Team
            <span className="ml-auto text-[10px] text-zinc-600">Members & memory</span>
          </button>
        )}

        <button
          onClick={onOpenSettings}
          className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
        >
          <span className="w-9 h-9 rounded-xl bg-violet-500/10 text-violet-300 inline-flex items-center justify-center">
            <Settings className="w-[18px] h-[18px]" />
          </span>
          Settings
          <span className="ml-auto text-[10px] text-zinc-600">System & access</span>
        </button>

        <button
          onClick={onClose}
          className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-medium text-zinc-300 hover:text-white hover:bg-white/[0.06] transition-colors"
        >
          <span className="w-9 h-9 rounded-xl bg-emerald-500/10 text-emerald-300 inline-flex items-center justify-center">
            <Shield className="w-[18px] h-[18px]" />
          </span>
          Close
          <span className="ml-auto text-[10px] text-zinc-600">Return to shell</span>
        </button>
      </div>

      {/* Sign out */}
      <div className="px-3 py-4 border-t border-white/[0.06]">
        <button
          onClick={() => { onClose(); logout(); }}
          className="w-full flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-medium text-rose-300/90 hover:text-rose-200 hover:bg-rose-500/[0.08] transition-colors"
        >
          <span className="w-9 h-9 rounded-xl bg-rose-500/10 text-rose-300 inline-flex items-center justify-center">
            <LogOut className="w-[18px] h-[18px]" />
          </span>
          Sign out
          <span className="ml-auto text-[10px] text-rose-400/50">End session</span>
        </button>
      </div>
    </div>
  );
}