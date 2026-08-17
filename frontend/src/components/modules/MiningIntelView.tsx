import { motion } from 'framer-motion';
import { Map, AlertTriangle, Coins } from 'lucide-react';
import { useMarketPrices } from '../../hooks/useMarketPrices';
import { SectionLabel } from '../ui/SectionLabel';
import { Sparkline } from '../ui/Sparkline';
import { Badge } from '../ui/Badge';
import { EmptyState } from '../ui/EmptyState';
import { Spinner } from '../ui/Spinner';
import { SpotlightCard } from '../ui/SpotlightCard';
import { AnimatedNumber } from '../ui/AnimatedNumber';
import type { MetalPrice } from '../../types';

const METALS: Array<{ key: string; name: string; unit: string }> = [
  { key: 'gold', name: 'Gold', unit: 'oz' },
  { key: 'silver', name: 'Silver', unit: 'oz' },
  { key: 'platinum', name: 'Platinum', unit: 'oz' },
  { key: 'palladium', name: 'Palladium', unit: 'oz' },
];

const GEMSTONES: Array<{ key: string; name: string }> = [
  { key: 'diamond_1ct_flawless', name: 'Diamond · 1ct Flawless' },
  { key: 'tanzanite_aaa', name: 'Tanzanite · AAA' },
  { key: 'ruby_pigeon_blood', name: 'Ruby · Pigeon Blood' },
  { key: 'emerald_fine', name: 'Emerald · Fine' },
  { key: 'tsavorite_vivid', name: 'Tsavorite · Vivid' },
];

const usd = (n: number) => `$${n.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

function trendSeries(m: MetalPrice | undefined): number[] {
  if (!m) return [];
  const a = m.change_7d ?? m.change_24h ?? 0;
  const b = m.change_24h ?? m.change_7d ?? 0;
  const pts: number[] = [];
  for (let i = 0; i < 14; i++) pts.push(a + (b - a) * (i / 13));
  return pts;
}

export function MiningIntelView() {
  const { data, error, loading } = useMarketPrices(60_000);
  const metals = data?.summary?.metals ?? {};
  const gemstones = data?.summary?.gemstones ?? {};
  const ratio = data?.summary?.gold_silver_ratio;
  const alerts = data?.summary?.alerts ?? [];

  return (
    <div className="h-full overflow-y-auto thin-scrollbar px-4 md:px-8 py-6">
      <div className="max-w-5xl mx-auto space-y-8 pb-8">
        <motion.header
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
          className="flex items-center gap-3.5"
        >
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-sky-500 to-violet-600 flex items-center justify-center shadow-[0_10px_28px_rgba(59,110,246,0.45)]">
            <Map className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-white tracking-tight">Mining Intelligence</h2>
            <p className="text-[13px] text-zinc-500">Live commodity markets and geological data</p>
          </div>
        </motion.header>

        {loading && !data ? (
          <div className="flex justify-center py-16 text-sky-300"><Spinner className="w-6 h-6" /></div>
        ) : error && !data ? (
          <div className="glass-faint rounded-2xl">
            <EmptyState
              icon={<AlertTriangle className="w-6 h-6" />}
              title="Market feed offline"
              description={error}
            />
          </div>
        ) : (
          <>
            {/* Metals */}
            <section className="space-y-4">
              <SectionLabel>Metals</SectionLabel>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                {METALS.map((m, i) => {
                  const meta = metals[m.key] as MetalPrice | undefined;
                  const change = meta?.change_24h ?? 0;
                  const positive = change >= 0;
                  return (
                    <motion.div
                      key={m.key}
                      initial={{ opacity: 0, y: 12 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: i * 0.06, type: 'spring', stiffness: 300, damping: 26 }}
                    >
                      <SpotlightCard className="glass-faint rounded-2xl h-full">
                        <div className="p-4 h-full flex flex-col">
                          <div className="flex items-center justify-between mb-3">
                            <span className="text-[12px] font-medium text-zinc-400">{m.name}</span>
                            <Badge tone={positive ? 'emerald' : 'rose'}>
                              {positive ? '+' : ''}{change.toFixed(2)}%
                            </Badge>
                          </div>
                          <div className="text-[22px] font-semibold text-white tracking-tight">
                            {meta ? <AnimatedNumber value={meta.price} format={usd} /> : '—'}
                          </div>
                          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5 font-mono">
                            {meta?.unit ?? m.unit} / USD
                          </div>
                          <div className="mt-3">
                            <Sparkline values={trendSeries(meta)} positive={positive} width={180} height={42} />
                          </div>
                        </div>
                      </SpotlightCard>
                    </motion.div>
                  );
                })}
              </div>
            </section>

            {/* Ratio + alerts */}
            <section className="grid grid-cols-1 lg:grid-cols-3 gap-3.5">
              <SpotlightCard className="glass-faint rounded-2xl">
                <div className="p-4 flex items-center gap-3.5">
                  <div className="w-10 h-10 rounded-xl bg-violet-400/10 text-violet-300 inline-flex items-center justify-center shrink-0">
                    <Coins className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="text-[11px] uppercase tracking-wider text-zinc-500 font-medium">Gold / Silver Ratio</div>
                    <div className="text-lg font-semibold text-white tabular">{ratio ?? '—'}</div>
                  </div>
                </div>
              </SpotlightCard>
              {alerts.length > 0 && (
                <SpotlightCard className="glass-faint rounded-2xl lg:col-span-2">
                  <div className="p-4 space-y-2">
                    <SectionLabel>Alerts</SectionLabel>
                    {alerts.map((a, i) => (
                      <div key={i} className="flex items-start gap-2.5 text-[13px] text-amber-200/90">
                        <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-300" />
                        {a}
                      </div>
                    ))}
                  </div>
                </SpotlightCard>
              )}
            </section>

            {/* Gemstones */}
            {Object.keys(gemstones).length > 0 && (
              <section className="space-y-4">
                <SectionLabel>Gemstones</SectionLabel>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
                  {GEMSTONES.filter((g) => gemstones[g.key]).map((g) => {
                    const meta = gemstones[g.key] as MetalPrice;
                    return (
                      <SpotlightCard key={g.key} className="glass-faint rounded-2xl">
                        <div className="p-4">
                          <div className="text-[12px] font-medium text-zinc-400">{g.name}</div>
                          <div className="text-lg font-semibold text-white tabular mt-1.5">
                            <AnimatedNumber value={meta.price} format={usd} />
                          </div>
                          <div className="text-[10px] text-zinc-600 uppercase tracking-wider mt-0.5 font-mono">
                            {meta.unit} / USD
                          </div>
                        </div>
                      </SpotlightCard>
                    );
                  })}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
