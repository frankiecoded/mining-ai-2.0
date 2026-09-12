import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Users,
  RefreshCw,
  Mail,
  X,
  Lock,
  Shield,
  KeyRound,
  Database,
  CheckCircle2,
  Clock,
  Phone,
  ChevronRight,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { useAuth } from '../../contexts/AuthContext';
import { Sheet } from '../ui/Sheet';
import type { TeamMember, MemoryProfile, MemoryFact } from '../../types';
import { Spinner } from '../ui/Spinner';
import { IconButton } from '../ui/IconButton';

const OWNER_USERNAME = 'frank';

function initialsOf(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .slice(0, 2)
    .join('');
}

function factEntries(profile: MemoryProfile | null): Array<[string, unknown]> {
  return Object.entries(profile ?? {}).filter(([k]) => k !== 'history');
}

function preferencesOf(profile: MemoryProfile | null): Array<[string, string]> {
  const prefs = profile?.preferences ?? {};
  return Object.entries(prefs);
}

function historyOf(profile: MemoryProfile | null): MemoryFact[] {
  return profile?.history ?? [];
}

/* ──────────────── Frank-only Member Detail Sheet ──────────────── */
function MemberDetail({
  member,
  onClose,
}: {
  member: TeamMember;
  onClose: () => void;
}) {
  const profile = member.memory_profile;
  const summary = factEntries(profile).filter(([k]) => k !== 'phone');
  const prefs = preferencesOf(profile);
  const history = historyOf(profile);

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const datasets = member.allowed_datasets?.length
    ? member.allowed_datasets
    : member.role === 'admin'
      ? ['*']
      : [];

  const isOwner = member.username === OWNER_USERNAME;

  return (
    <Sheet open onClose={onClose} side="right" width="w-[400px] sm:w-[420px]">
      <div className="h-full flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-400" />
            <h3 className="text-[13px] font-semibold text-white tracking-tight">
              Member Profile
            </h3>
            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-400/10 text-emerald-300 border border-emerald-400/20">
              Frank Only
            </span>
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X className="w-4 h-4" />
          </IconButton>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 min-h-0 overflow-y-auto thin-scrollbar px-5 py-6 space-y-6">
          {/* Identity */}
          <div className="glass-strong rounded-2xl border border-white/[0.06] p-5">
            <div className="flex items-center gap-4">
              <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center text-lg font-bold text-white shadow-[0_12px_28px_rgba(59,110,246,0.45)] shrink-0">
                {initialsOf(member.display_name || member.username)}
              </div>
              <div className="min-w-0">
                <div className="text-base font-semibold text-white tracking-tight truncate">
                  {member.display_name || member.username}
                </div>
                <div className="text-[12px] text-zinc-500 font-mono">
                  @{member.username}
                </div>
                {member.email ? (
                  <a
                    href={`mailto:${member.email}`}
                    className="text-[12px] text-sky-300 hover:text-sky-200 flex items-center gap-1.5 mt-0.5"
                  >
                    <Mail className="w-3 h-3" />
                    <span className="truncate">{member.email}</span>
                  </a>
                ) : (
                  <div className="text-[12px] text-zinc-600 mt-0.5 flex items-center gap-1.5">
                    <Mail className="w-3 h-3" />
                    No email on file
                  </div>
                )}
              </div>
            </div>

            {/* Badges */}
            <div className="flex flex-wrap items-center gap-1.5 mt-4">
              <span className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-sky-500/15 text-sky-300">
                {member.role_title || 'Team Member'}
              </span>
              <span
                className={`text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-lg border ${
                  member.role === 'admin'
                    ? 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20'
                    : 'bg-zinc-500/10 text-zinc-300 border-zinc-500/20'
                }`}
              >
                {member.role === 'admin' ? 'Admin' : 'Member'} Access
              </span>
              {isOwner && (
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-amber-400/10 text-amber-300 border border-amber-400/20">
                  Owner
                </span>
              )}
              {member.provisioned ? (
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-white/[0.05] text-zinc-300 border border-white/[0.08]">
                  <CheckCircle2 className="w-3 h-3 inline mr-1" />
                  Team Account
                </span>
              ) : (
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-lg bg-white/[0.05] text-zinc-400 border border-white/[0.08]">
                  Built-in
                </span>
              )}
            </div>
          </div>

          {/* Account */}
          <div className="glass rounded-2xl p-5 space-y-3">
            <div className="flex items-center gap-2">
              <KeyRound className="w-4 h-4 text-violet-400" />
              <h4 className="text-[12px] font-semibold text-white uppercase tracking-wider">
                Account
              </h4>
            </div>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-zinc-500">Tenant ID</span>
                <span className="text-white font-mono">{member.tenant_id}</span>
              </div>
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-zinc-500">Username</span>
                <span className="text-white font-mono">@{member.username}</span>
              </div>
              <div className="flex items-center justify-between text-[12px]">
                <span className="text-zinc-500">Profile</span>
                <span className="text-white font-medium">
                  {member.provisioned ? 'Provisioned' : 'Built-in'}
                </span>
              </div>
            </div>

            {/* Allowed datasets */}
            <div className="pt-1">
              <div className="text-[12px] text-zinc-500 mb-2 flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5" />
                Access to datasets
              </div>
              {datasets.length === 0 ? (
                <p className="text-[12px] text-zinc-600 italic">No dataset access.</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {datasets.map((d) => (
                    <span
                      key={d}
                      className="px-2 py-0.5 rounded-lg bg-white/[0.04] text-zinc-300 text-[11px] font-mono border border-white/[0.06]"
                    >
                      {d}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Memory */}
          <div className="glass rounded-2xl p-5 space-y-4">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-sky-400" />
              <h4 className="text-[12px] font-semibold text-white uppercase tracking-wider">
                Stored Intelligence
              </h4>
              <span className="ml-auto text-[10px] text-zinc-600">
                {profile ? Object.keys(profile).length : 0} bucket(s)
              </span>
            </div>

            {!profile ? (
              <p className="text-[12px] text-zinc-500 italic">
                No stored facts yet for this person.
              </p>
            ) : (
              <div className="space-y-4">
                {/* Phone */}
                {(profile.phone || '').trim() && (
                  <div className="flex items-center gap-2 text-[12px]">
                    <Phone className="w-3.5 h-3.5 text-zinc-500" />
                    <span className="font-medium text-zinc-400">Phone</span>
                    <span className="text-white font-mono ml-auto">
                      {profile.phone}
                    </span>
                  </div>
                )}

                {/* Key facts / preferences */}
                {prefs.length > 0 && (
                  <div className="space-y-1.5">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      Preferences & Facts
                    </div>
                    {prefs.map(([k, v]) => (
                      <div key={k} className="flex items-start gap-2 text-[12px]">
                        <span className="shrink-0 font-medium text-zinc-400 capitalize min-w-[26%] truncate">
                          {k.replace(/_/g, ' ')}
                        </span>
                        <span className="text-zinc-200/90 break-words">{v}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Other buckets */}
                {summary.length > 0 && (
                  <div className="space-y-1.5">
                    {summary.map(([k, v]) => (
                      <div key={k} className="flex items-start gap-2 text-[12px]">
                        <span className="shrink-0 font-medium text-zinc-400 capitalize min-w-[26%] truncate">
                          {k.replace(/_/g, ' ')}
                        </span>
                        <span className="text-zinc-200/90 break-words">
                          {typeof v === 'object' && v !== null
                            ? JSON.stringify(v)
                            : String(v)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* History timeline */}
                {history.length > 0 && (
                  <div className="space-y-0">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
                      <Clock className="w-3 h-3" />
                      Interaction History
                    </div>
                    <ul className="relative border-l border-white/[0.08] ml-1.5 space-y-3">
                      {history.map((fact, i) => (
                        <li key={i} className="pl-4 relative">
                          <span className="absolute -left-[4.5px] top-1.5 w-[7px] h-[7px] rounded-full bg-sky-400/70 shadow-[0_0_8px_rgba(56,189,248,0.6)]" />
                          <div className="text-[12px] font-medium text-zinc-200">
                            {fact.title}
                          </div>
                          <div className="text-[11px] text-zinc-500 leading-relaxed line-clamp-3">
                            {fact.content}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {prefs.length === 0 && summary.length === 0 && history.length === 0 && (
                  <p className="text-[12px] text-zinc-500 italic">
                    No stored facts yet for this person.
                  </p>
                )}
              </div>
            )}
          </div>

          <p className="text-[11px] text-zinc-600 flex items-center gap-1.5 px-1">
            <Lock className="w-3 h-3" />
            Restricted to the system owner ({OWNER_USERNAME}).
          </p>
        </div>
      </div>
    </Sheet>
  );
}

/* ──────────────────────────── Team Module ──────────────────────────── */
export function TeamView() {
  const { user, token } = useAuth();
  const [members, setMembers] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<TeamMember | null>(null);

  const isOwner = user?.username === OWNER_USERNAME;

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

  useEffect(() => {
    if (!isOwner) setSelected(null);
  }, [isOwner]);

  if (user?.role !== 'admin') {
    return (
      <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
        You don’t have access to the team view.
      </div>
    );
  }

  return (
    <div className="h-full overflow-hidden flex flex-col relative">
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
                  onClick={() => isOwner && setSelected(m)}
                  role={isOwner ? 'button' : undefined}
                  tabIndex={isOwner ? 0 : undefined}
                  onKeyDown={
                    isOwner
                      ? (e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setSelected(m);
                          }
                        }
                      : undefined
                  }
                  className={`glass-strong rounded-2xl border border-white/[0.06] p-4 transition-all ${
                    isOwner
                      ? 'cursor-pointer hover:border-sky-400/25 hover:bg-white/[0.02] focus-visible:ring-2 ring-sky-400/40 outline-none'
                      : 'cursor-default'
                  }`}
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
                        <span className="truncate">{m.email || 'no email'}</span>
                      </div>
                    </div>
                    {isOwner && (
                      <span className="flex items-center gap-0.5 text-[11px] text-sky-300 shrink-0">
                        <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1.5 mb-2.5">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
                      {m.role_title || 'Team Member'}
                    </span>
                    <span className="ml-auto text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-lg bg-sky-500/15 text-sky-300">
                      {m.role === 'admin' ? 'Admin' : 'Member'}
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
                          <span className="text-zinc-200/90 break-words">
                            {typeof v === 'object' && v !== null ? JSON.stringify(v) : String(v)}
                          </span>
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

        {!isOwner && (
          <p className="text-[11px] text-zinc-600 flex items-center gap-1.5 mt-4">
            <Lock className="w-3 h-3" />
            Member profiles are only accessible by the system owner.
          </p>
        )}
      </div>

      {/* Frank-only detail sheet */}
      {isOwner && selected && (
        <MemberDetail member={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}