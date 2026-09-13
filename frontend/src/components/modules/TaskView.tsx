import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FolderKanban, Plus, Loader2, Play, CheckCircle2, Clock, AlertTriangle, RefreshCw } from 'lucide-react';
import { useTasks } from '../../hooks/useTasks';
import { GlassPanel } from '../ui/GlassPanel';
import { SectionLabel } from '../ui/SectionLabel';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';
import { Spinner } from '../ui/Spinner';
import { StatCard } from '../ui/StatCard';
import type { Task } from '../../types';

const statusTone: Record<string, 'emerald' | 'sky' | 'amber' | 'rose'> = {
  completed: 'emerald',
  running: 'sky',
  pending: 'amber',
};

const statusIcon = (status: string) => {
  switch (status) {
    case 'completed': return <CheckCircle2 className="w-4 h-4 text-emerald-400" />;
    case 'running': return <Play className="w-4 h-4 text-sky-400" />;
    default: return <Clock className="w-4 h-4 text-amber-400" />;
  }
};

export function TaskView() {
  const { tasks, loading, error, createTask } = useTasks(10_000);
  const [desc, setDesc] = useState('');
  const [creating, setCreating] = useState(false);
  const [rerunning, setRerunning] = useState<string | null>(null);

  const statusOf = (t: Task) => (t.status || 'pending');
  const counts = {
    total: tasks.length,
    running: tasks.filter((t) => statusOf(t) === 'running').length,
    completed: tasks.filter((t) => statusOf(t) === 'completed').length,
    pending: tasks.filter((t) => statusOf(t) === 'pending').length,
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!desc.trim() || creating) return;
    setCreating(true);
    try {
      await createTask(desc.trim(), 'auto-orchestrator');
      setDesc('');
    } finally {
      setCreating(false);
    }
  };

  const rerun = async (t: Task) => {
    if (rerunning) return;
    setRerunning(t.id);
    try {
      await createTask(t.description, t.assignee ?? t.assigned_to ?? 'auto-orchestrator');
    } finally {
      setRerunning(null);
    }
  };

  const timeStr = (t: Task) => {
    if (!t.created_at) return null;
    return new Date(t.created_at).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-4xl mx-auto space-y-8 pb-8">
        <header className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_10px_28px_rgba(59,110,246,0.45)]">
            <FolderKanban className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white tracking-tight">Operations</h2>
            <p className="text-[13px] text-zinc-500">Task orchestrator and worker queue</p>
          </div>
        </header>

        {/* Live queue metrics — at-a-glance health of the operation */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={<FolderKanban className="w-4 h-4" />} label="Total Objectives" value={String(counts.total)} tone="sky" animate={counts.total} />
          <StatCard icon={<Play className="w-4 h-4" />} label="Running Now" value={String(counts.running)} tone="sky" animate={counts.running} />
          <StatCard icon={<CheckCircle2 className="w-4 h-4" />} label="Completed" value={String(counts.completed)} tone="emerald" animate={counts.completed} />
          <StatCard icon={<Clock className="w-4 h-4" />} label="Pending" value={String(counts.pending)} tone="zinc" animate={counts.pending} />
        </section>

        <section className="space-y-4">
          <SectionLabel>New Objective</SectionLabel>
          <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3">
            <input
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="e.g. Analyze the latest geology report"
              className="glass-input rounded-xl px-4 py-3 flex-1 text-sm text-white placeholder-zinc-600"
            />
            <button
              type="submit"
              disabled={creating || !desc.trim()}
              className="btn-primary rounded-xl px-5 py-3 text-sm font-semibold flex items-center justify-center gap-2 shrink-0"
            >
              {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
              Assign Worker
            </button>
          </form>
        </section>

        <section className="space-y-4">
          <SectionLabel>Queue</SectionLabel>

          {error && (
            <div className="flex items-start gap-2.5 rounded-xl p-3.5 text-[13px] bg-amber-400/10 text-amber-200">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              {error}
            </div>
          )}

          {loading && tasks.length === 0 ? (
            <div className="flex justify-center py-12 text-sky-300"><Spinner className="w-6 h-6" /></div>
          ) : tasks.length === 0 ? (
            <GlassPanel tone="faint">
              <EmptyState
                icon={<FolderKanban className="w-6 h-6" />}
                title="Queue is clear"
                description="New objectives will appear here as they are assigned."
              />
            </GlassPanel>
          ) : (
            <div className="space-y-2.5">
              <AnimatePresence initial={false}>
                {tasks.map((task, i) => (
                  <motion.div
                    key={task.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ delay: Math.min(i * 0.04, 0.3) }}
                  >
                    <GlassPanel tone="faint" className="p-4 flex items-center justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <span className="mt-0.5 shrink-0">{statusIcon(statusOf(task))}</span>
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-white break-words">{task.description}</div>
                          <div className="flex items-center gap-3 mt-1 text-[11px] text-zinc-600 font-mono">
                            <span>ID · {task.id.slice(0, 8)}</span>
                            <span className="hidden sm:inline">NODE · {task.assignee ?? task.assigned_to ?? 'Unassigned'}</span>
                            {timeStr(task) && <span className="hidden sm:inline">CREATED · {timeStr(task)}</span>}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => void rerun(task)}
                          disabled={rerunning === task.id}
                          title="Queue the same objective again"
                          className="p-2 rounded-lg glass-faint text-zinc-500 hover:text-sky-300 hover:bg-white/[0.08] transition-colors"
                        >
                          {rerunning === task.id ? (
                            <Loader2 className="w-4 h-4 animate-spin text-sky-300" />
                          ) : (
                            <RefreshCw className="w-4 h-4" />
                          )}
                        </button>
                        <Badge tone={statusTone[statusOf(task)] ?? 'rose'} className="shrink-0 capitalize">
                          {statusOf(task)}
                        </Badge>
                      </div>
                    </GlassPanel>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
