import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Users, RefreshCw, Mail } from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import type { TeamMember } from '../../types';
import { Spinner } from '../ui/Spinner';
import { IconButton } from '../ui/IconButton';

function initialsOf(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('');
}

export function TeamView() {
  const { user, token } = useAuth();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (user?.role !== 'admin' || !token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await ChatAPI.fetchTeam();
      if (res.status === 'success') {
        setMembers(res.members || []);
      } else {
        setError(res instanceof Error ? res.message : 'Failed to load team.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load team.');
    } finally {
      setLoading(false);
    }
  }, [user, token]);

  useEffect(() => {
    void load();
  }, [load]);

  if (user?.role !== 'admin') {
    return (
      <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
        You don’t have access to the team view.
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden flex flex-col app-aurora app-grain relative">
      <div className="aurora-blob w-[360px] h-[360px] top-1/4 -right-24 bg-sky-600/30" />

      {/* Header */}
      <div className="flex items-center justify-between px-5 md:px-8 pt-6 pb-4 relative z-10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[14px] bg-gradient-to-br from-sky-500/80 to-violet-600/80 shadow-[0_8px_20px_rgba(59,110,246,0.4)] flex items-center justify-center">
            <Users className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-[17px] font-semibold text-white tracking-tight">Team</h2>
            <p className="text-[11px] text-zinc-500 font-medium">{members.length} account(s)</p>
          </div>
        </div>
        <IconButton label="Refresh team" onClick={() => void load()}>
          <RefreshCw className="w-4 h-4" />
        </IconButton>
      </div>

      {/* Cards */}
      <div className="flex-1 min-h-0 overflow-y-auto px-5 md:px-8 pb-8 relative z-10">
        {loading ? (
          <div className="h-40 flex items-center justify-center text-sky-300">
            <Spinner className="w-6 h-6" />
          </div>
        ) : error ? (
          <div className="text-[13px] text-rose-300 bg-rose-500/10 border border-rose-500/20 rounded-xl p-3">
            {error}
          </div>
        ) : members.length === 0 ? (
          <p className="text-sm text-zinc-500 mt-8">
            No team accounts yet. Accounts created via the signup page appear here.
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {members.map((m, i) => {
              const memoryEntries = Object.entries(m.memory_profile || {}).filter(
                ([k]) => k !== 'history',
              );
              return (
                <motion.div
                  key={m.username}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="glass-strong rounded-2xl border border-white/[0.06] p-4"
                >
                  <div className="flex items-center gap-3 mb-3">
                    <div className="h-10 w-10 rounded-full bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center text-[12px] font-bold text-white">
                      {initialsOf(m.display_name || m.username)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-white truncate">
                        {m.display_name || m.username}
                      </div>
                      <div className="text-[11px] text-zinc-400 flex items-center gap-1">
                        <Mail className="w-3 h-3" />
                        <span className="truncate">{m.email}</span>
                      </div>
                    </div>
                    <div>
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-lg bg-sky-500/15 text-sky-300">
                        {m.role_title || 'Team Member'}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5 mb-2.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      Memory
                    </span>
                  </div>
                  {memoryEntries.length === 0 ? (
                    <p className="text-[12px] text-zinc-500 italic">No stored facts yet.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {memoryEntries.slice(0, 6).map(([k, v]) => (
                        <div key={k} className="flex items-start gap-2 text-[12px]">
                          <span className="shrink-0 font-medium text-zinc-400 capitalize min-w-[24%] truncate">
                            {k.replace(/_/g, ' ')}
                          </span>
                          <span className="text-zinc-200/90 break-words">{String(v)}</span>
                        </div>
                      ))}
                      {memoryEntries.length > 6 && (
                        <p className="text-[11px] text-zinc-500">
                          +{memoryEntries.length - 6} more facts
                        </p>
                      )}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}