import { useCallback, useEffect, useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Landmark, Plus, Loader2, CheckCircle2, AlertCircle, Wallet, Hourglass,
  RefreshCw, CircleDollarSign, PiggyBank, TrendingUp, Coins,
} from 'lucide-react';
import { ChatAPI } from '../../services/api';
import { useMarketPrices } from '../../hooks/useMarketPrices';
import { GlassPanel } from '../ui/GlassPanel';
import { SectionLabel } from '../ui/SectionLabel';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';
import { StatCard } from '../ui/StatCard';
import { SpotlightCard } from '../ui/SpotlightCard';
import { AnimatedNumber } from '../ui/AnimatedNumber';
import type { ProcurementRecord } from '../../types';

const currency = (n: number) =>
  n.toLocaleString(undefined, { style: 'currency', currency: 'USD', minimumFractionDigits: 2 });

type FinTab = 'ledger' | 'budgets';

export function FinanceView() {
  const { data: market } = useMarketPrices();
  const [tab, setTab] = useState<FinTab>('ledger');

  const [item, setItem] = useState('');
  const [cost, setCost] = useState('');
  const [records, setRecords] = useState<ProcurementRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [message, setMessage] = useState('');

  const loadLedger = useCallback(async () => {
    try {
      const res = await ChatAPI.fetchProcurements();
      setRecords(res.records || []);
    } catch {
      // silent — ledger stays empty; the form still works
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void loadLedger(); }, [loadLedger]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const value = Number(cost);
    if (!item.trim() || !(value > 0) || submitting) return;

    setSubmitting(true);
    setStatus('idle');
    try {
      await ChatAPI.submitProcurement(item.trim(), value);
      setItem('');
      setCost('');
      setStatus('success');
      setMessage('Procurement request logged with the Finance Engine.');
      await loadLedger();
    } catch (err) {
      setStatus('error');
      setMessage(err instanceof Error ? err.message : 'Failed to submit procurement.');
    } finally {
      setSubmitting(false);
    }
  };

  const totalRequested = records.reduce((sum, r) => sum + (Number(r.cost) || 0), 0);
  const pendingCount = records.filter((r) => r.status === 'pending_approval').length;
  const approvedSum = records.filter((r) => r.status === 'approved').reduce((s, r) => s + (Number(r.cost) || 0), 0);
  const avgRequest = records.length ? totalRequested / records.length : 0;
  const maxRequest = records.reduce((m, r) => Math.max(m, Number(r.cost) || 0), 0);
  const statusOf = (r: ProcurementRecord) => (r.status === 'approved' ? 'Approved' : 'Pending Approval');

  const breakdown = useMemo(
    () =>
      [...records]
        .sort((a, b) => (Number(b.cost) || 0) - (Number(a.cost) || 0))
        .slice(0, 12),
    [records],
  );

  // Illustrative valuation from the live market feed (currency as reported).
  const goldUsd = Number(market?.summary?.metals?.gold?.price || 0);
  const silverUsd = Number(market?.summary?.metals?.silver?.price || 0);
  const metalValue = (goldUsd > 0 ? goldUsd : 0) + (silverUsd > 0 ? silverUsd * 0.08 : 0); // scout-grade estimate

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-4xl mx-auto space-y-8 pb-8">
        <header className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_10px_28px_rgba(59,110,246,0.45)]">
              <Landmark className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-semibold text-white tracking-tight">Finance Engine</h2>
              <p className="text-[13px] text-zinc-500">Procurement ledger and resource allocation</p>
            </div>
          </div>
          <div className="flex items-center gap-2 p-1 rounded-full glass-faint">
            {(['ledger', 'budgets'] as FinTab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`px-4 py-1.5 rounded-full text-[13px] font-medium transition-colors ${
                  tab === t ? 'bg-white/[0.12] text-white' : 'text-zinc-500 hover:text-white'
                }`}
              >
                {t === 'ledger' ? 'Ledger' : 'Budgets & Costs'}
              </button>
            ))}
          </div>
        </header>

        {/* Budget summary — live from the persistent ledger */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatCard icon={<Wallet className="w-4 h-4" />} label="Total Requested" value={currency(totalRequested)} tone="sky" />
          <StatCard icon={<CircleDollarSign className="w-4 h-4" />} label="Requests" value={String(records.length)} tone="zinc" animate={records.length} />
          <StatCard icon={<Hourglass className="w-4 h-4" />} label="Pending Approval" value={String(pendingCount)} tone="zinc" animate={pendingCount} />
          <StatCard icon={<CheckCircle2 className="w-4 h-4" />} label="Approved" value={currency(approvedSum)} tone="emerald" />
        </section>

        {tab === 'ledger' && (
          <>
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
              <div className="flex items-center justify-between">
                <SectionLabel>Ledger</SectionLabel>
                <button
                  onClick={() => void loadLedger()}
                  className="p-2 -m-1 rounded-full text-zinc-600 hover:text-white hover:bg-white/[0.08] transition-colors"
                  title="Refresh ledger"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                </button>
              </div>

              {loading && records.length === 0 ? (
                <div className="flex justify-center py-12 text-sky-300"><Loader2 className="w-6 h-6 animate-spin" /></div>
              ) : records.length === 0 ? (
                <GlassPanel tone="faint">
                  <EmptyState
                    icon={<Landmark className="w-6 h-6" />}
                    title="No procurement entries"
                    description="Submit a procurement request and it will be logged here permanently."
                  />
                </GlassPanel>
              ) : (
                <div className="space-y-2.5">
                  <AnimatePresence initial={false}>
                    {records.map((p, i) => (
                      <motion.div
                        key={p.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(i * 0.04, 0.3) }}
                      >
                        <GlassPanel tone="faint" className="p-4 flex items-center justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-sm font-medium text-white truncate">{p.item}</div>
                            <div className="text-[11px] text-zinc-600 font-mono mt-0.5 tabular break-words">
                              {new Date(p.time).toLocaleString()}
                              {p.requested_by && p.requested_by !== 'authenticated_user' ? ` · ${p.requested_by}` : ''}
                            </div>
                          </div>
                          <div className="flex items-center gap-3 shrink-0">
                            <span className="text-[15px] font-semibold text-white tabular">{currency(Number(p.cost))}</span>
                            <Badge tone={p.status === 'approved' ? 'emerald' : 'amber'}>{statusOf(p)}</Badge>
                          </div>
                        </GlassPanel>
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              )}
            </section>
          </>
        )}

        {tab === 'budgets' && (
          <>
            <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <StatCard icon={<TrendingUp className="w-4 h-4" />} label="Average Request" value={currency(avgRequest)} tone="zinc" />
              <StatCard icon={<PiggyBank className="w-4 h-4" />} label="Largest Single" value={currency(maxRequest)} tone="zinc" />
              <StatCard icon={<Coins className="w-4 h-4" />} label="Gold (USD/oz)" value={goldUsd ? currency(goldUsd) : '—'} tone="sky" />
              <StatCard icon={<Coins className="w-4 h-4" />} label="Silver (USD/oz)" value={silverUsd ? currency(silverUsd) : '—'} tone="zinc" />
            </section>

            <section className="space-y-4">
              <SectionLabel>Cost Breakdown</SectionLabel>
              {records.length === 0 ? (
                <GlassPanel tone="faint">
                  <EmptyState
                    icon={<PiggyBank className="w-6 h-6" />}
                    title="Nothing budgeted yet"
                    description="Submit procurement requests on the Ledger tab and the breakdown will appear here."
                  />
                </GlassPanel>
              ) : (
                <GlassPanel tone="faint" className="p-4 space-y-3">
                  {breakdown.map((r, i) => {
                    const costNum = Number(r.cost) || 0;
                    const share = totalRequested ? (costNum / totalRequested) * 100 : 0;
                    return (
                      <div key={r.id}>
                        <div className="flex items-center justify-between gap-3 mb-1">
                          <span className="text-[13px] text-zinc-300 truncate">{r.item}</span>
                          <span className="text-[13px] font-semibold text-white tabular shrink-0">{currency(costNum)}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${share}%` }}
                            transition={{ delay: i * 0.05, duration: 0.5, ease: 'easeOut' }}
                            className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500"
                          />
                        </div>
                        <span className="text-[10px] text-zinc-600 font-mono">{share.toFixed(1)}% of budget</span>
                      </div>
                    );
                  })}
                </GlassPanel>
              )}
            </section>

            <section className="space-y-4">
              <SectionLabel>Scout Value Estimate</SectionLabel>
              <SpotlightCard className="glass-faint rounded-2xl">
                <div className="p-4 md:p-5">
                  <div className="text-[26px] font-semibold text-white tabular flex items-center gap-2">
                    <AnimatedNumber value={metalValue} format={currency} />
                    <span className="text-[12px] font-medium text-zinc-500 normal-case">/ scout sample (illustrative)</span>
                  </div>
                  <p className="text-[12.5px] text-zinc-500 mt-2 leading-relaxed">
                    Blends the live gold and silver spot feed into a rough per-sample working value so field
                    reports translate into money. Refresh the market feed for exact figures.
                  </p>
                </div>
              </SpotlightCard>
            </section>
          </>
        )}
      </div>
    </div>
  );
}