import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Landmark, Plus, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { GlassPanel } from '../ui/GlassPanel';
import { SectionLabel } from '../ui/SectionLabel';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';

interface ProcurementItem {
  id: string;
  item: string;
  cost: number;
  time: string;
}

export function FinanceView() {
  const [item, setItem] = useState('');
  const [cost, setCost] = useState('');
  const [items, setItems] = useState<ProcurementItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = Number(cost);
    if (!item.trim() || !(value > 0)) return;

    setSubmitting(true);
    setStatus('idle');
    try {
      await ChatAPI.submitProcurement(item.trim(), value);
      setItems((prev) => [
        { id: crypto.randomUUID(), item: item.trim(), cost: value, time: new Date().toISOString() },
        ...prev,
      ]);
      setItem('');
      setCost('');
      setStatus('success');
      setMessage('Procurement request submitted to the Finance Engine.');
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Failed to submit procurement.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-4xl mx-auto space-y-8 pb-8">
        <header className="flex items-center gap-3.5">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_10px_28px_rgba(59,110,246,0.45)]">
            <Landmark className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white tracking-tight">Finance Engine</h2>
            <p className="text-[13px] text-zinc-500">Procurement and resource allocation</p>
          </div>
        </header>

        <section className="space-y-4">
          <SectionLabel>Procurement Request</SectionLabel>
          <GlassPanel className="p-5">
            <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <input
                value={item}
                onChange={(e) => setItem(e.target.value)}
                placeholder="Item, e.g. Drilling consumables"
                className="glass-input rounded-xl px-4 py-3 text-sm text-white placeholder-zinc-600 sm:col-span-2"
              />
              <div className="relative sm:col-span-1">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 text-sm">$</span>
                <input
                  value={cost}
                  onChange={(e) => setCost(e.target.value)}
                  inputMode="decimal"
                  placeholder="Estimated cost"
                  className="glass-input rounded-xl pl-8 pr-4 py-3 w-full text-sm text-white placeholder-zinc-600"
                />
              </div>
              <button
                type="submit"
                disabled={submitting || !item.trim() || !(Number(cost) > 0)}
                className="btn-primary rounded-xl px-5 py-3 text-sm font-semibold flex items-center justify-center gap-2"
              >
                {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Submit Request
              </button>
            </form>

            <AnimatePresence>
              {status !== 'idle' && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <div className={`mt-4 flex items-start gap-2.5 rounded-xl p-3.5 text-[13px] ${
                    status === 'success' ? 'bg-emerald-400/10 text-emerald-200' : 'bg-rose-400/10 text-rose-200'
                  }`}>
                    {status === 'success'
                      ? <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
                      : <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />}
                    {message}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </GlassPanel>
        </section>

        <section className="space-y-4">
          <SectionLabel>Request Log</SectionLabel>
          {items.length === 0 ? (
            <GlassPanel tone="faint">
              <EmptyState
                icon={<Landmark className="w-6 h-6" />}
                title="No requests submitted"
                description="Submit a procurement request and it will appear here."
              />
            </GlassPanel>
          ) : (
            <div className="space-y-2.5">
              {items.map((p) => (
                <motion.div
                  key={p.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                >
                  <GlassPanel tone="faint" className="p-4 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-white truncate">{p.item}</div>
                      <div className="text-[11px] text-zinc-600 font-mono mt-0.5 tabular">
                        {new Date(p.time).toLocaleString()}
                      </div>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-[15px] font-semibold text-white tabular">
                        ${p.cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </span>
                      <Badge tone="sky">Submitted</Badge>
                    </div>
                  </GlassPanel>
                </motion.div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
