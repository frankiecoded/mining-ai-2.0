import type { ReactNode } from 'react';
import { Cpu, Server, Database, Network, Activity, AlertTriangle, Gauge } from 'lucide-react';
import { useTelemetry } from '../../hooks/useTelemetry';
import { useMarketPrices } from '../../hooks/useMarketPrices';
import { SectionLabel } from '../ui/SectionLabel';
import { StatCard } from '../ui/StatCard';
import { Badge } from '../ui/Badge';
import { ProgressBar } from '../ui/ProgressBar';
import { Sparkline } from '../ui/Sparkline';
import { Skeleton } from '../ui/Skeleton';
import { StatusDot } from '../ui/StatusDot';
import type { MetalPrice } from '../../types';

const METAL_NAMES: Record<string, string> = {
  gold: 'Gold',
  silver: 'Silver',
  platinum: 'Platinum',
  palladium: 'Palladium',
};

function trendSeries(m: MetalPrice | undefined): number[] {
  if (!m) return [];
  const a = m.change_7d ?? m.change_24h ?? 0;
  const b = m.change_24h ?? m.change_7d ?? 0;
  const pts: number[] = [];
  for (let i = 0; i < 14; i++) pts.push(a + (b - a) * (i / 13));
  return pts;
}

export function RightPanel({ className = '' }: { className?: string }) {
  const { data: telemetry, error: telError } = useTelemetry(10_000);
  const { data: market, error: marketError } = useMarketPrices(60_000);

  const metals = market?.summary?.metals ?? {};
  const alerts = market?.summary?.alerts ?? [];
  const connected = !telError && !marketError;

  return (
    <div className={`w-80 shrink-0 h-full flex flex-col border-l border-white/[0.06] bg-white/[0.02] backdrop-blur-2xl ${className}`}>
      <div className="px-5 pt-5 pb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-white tracking-tight">System Pulse</h2>
          <span className="flex items-center gap-1.5 text-[11px] font-medium">
            <StatusDot online={connected} />
            <span className={connected ? 'text-emerald-300' : 'text-rose-300'}>
              {connected ? 'Live' : 'Offline'}
            </span>
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto thin-scrollbar px-4 pb-6 space-y-6">
        {!connected && (
          <div className="glass-faint rounded-2xl p-3.5 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-amber-300 mt-0.5 shrink-0" />
            <p className="text-xs text-zinc-400">{telError ?? marketError ?? 'Connecting…'}</p>
          </div>
        )}

        {/* System load */}
        <section className="space-y-3">
          <SectionLabel>System Load</SectionLabel>
          {!telemetry ? (
            <div className="grid grid-cols-2 gap-3">
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
              <Skeleton className="h-24" />
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                icon={<Cpu className="w-4 h-4" />}
                label="CPU"
                value={`${Math.round(telemetry.cpu_percent)}%`}
                tone="sky"
                animate={telemetry.cpu_percent}
              />
              <StatCard
                icon={<Server className="w-4 h-4" />}
                label="Memory"
                value={`${telemetry.memory_gb} GB`}
                tone="violet"
                animate={telemetry.memory_gb}
              />
              <StatCard
                icon={<Database className="w-4 h-4" />}
                label="Vector DB"
                value={`${telemetry.vector_latency_ms} ms`}
                tone="emerald"
                animate={telemetry.vector_latency_ms}
              />
              <StatCard
                icon={<Network className="w-4 h-4" />}
                label="Network"
                value={`${telemetry.network_gbps} Gbps`}
                tone="zinc"
                animate={telemetry.network_gbps}
              />
            </div>
          )}
        </section>

        {/* Markets */}
        <section className="space-y-3">
          <SectionLabel>Market Intelligence</SectionLabel>
          <div className="space-y-2.5">
            {!market ? (
              <>
                <Skeleton className="h-[86px]" />
                <Skeleton className="h-[86px]" />
              </>
            ) : (
              (['gold', 'silver', 'platinum', 'palladium'] as const).map((key) => {
                const m = metals[key];
                if (!m) return null;
                const change = m.change_24h ?? 0;
                const positive = change >= 0;
                return (
                  <div key={key} className="glass-faint rounded-2xl p-3.5 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[11px] uppercase tracking-wider text-zinc-500 font-medium">
                        {METAL_NAMES[key]}
                      </div>
                      <div className="text-[17px] font-semibold text-white tabular tracking-tight mt-0.5">
                        ${m.price.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </div>
                      <div className={`text-[11px] font-medium tabular mt-0.5 ${positive ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {positive ? '+' : ''}{change.toFixed(2)}% · 24h
                      </div>
                    </div>
                    <Sparkline values={trendSeries(m)} positive={positive} width={110} height={40} />
                  </div>
                );
              })
            )}
          </div>
        </section>

        {/* Subsystems */}
        <section className="space-y-3">
          <SectionLabel>Subsystems</SectionLabel>
          <div className="space-y-3.5">
            <SubsystemRow
              icon={<Activity className="w-4 h-4" />}
              name="Inference Engine"
              status={telemetry?.llm_status ?? 'Standby'}
              detail={telemetry ? `MODEL · ${telemetry.llm_model}` : undefined}
              online={(telemetry?.llm_status ?? '') === 'Online'}
            />
            <SubsystemRow
              icon={<Database className="w-4 h-4" />}
              name="Memory Core"
              status={telemetry?.memory_core_status ?? 'Indexing'}
              progress={telemetry?.memory_core_status === 'Online' ? 100 : 65}
              online={(telemetry?.memory_core_status ?? '') === 'Online'}
            />
            <SubsystemRow
              icon={<Gauge className="w-4 h-4" />}
              name="Task Worker"
              status={telemetry && telemetry.active_tasks > 0 ? 'Active' : 'Standby'}
              detail={`${telemetry?.active_tasks ?? 0} queued`}
              online={(telemetry?.active_tasks ?? 0) > 0}
            />
          </div>
        </section>

        {/* Alerts */}
        {alerts.length > 0 && (
          <section className="space-y-2.5">
            <SectionLabel>Alerts</SectionLabel>
            {alerts.map((alert, i) => (
              <div key={i} className="glass-faint rounded-2xl p-3.5 flex items-start gap-3">
                <AlertTriangle className="w-4 h-4 text-amber-300 mt-0.5 shrink-0" />
                <p className="text-xs text-zinc-300">{alert}</p>
              </div>
            ))}
          </section>
        )}
      </div>
    </div>
  );
}

function SubsystemRow({
  icon,
  name,
  status,
  detail,
  progress,
  online,
}: {
  icon: ReactNode;
  name: string;
  status: string;
  detail?: string;
  progress?: number;
  online?: boolean;
}) {
  return (
    <div className="glass-faint rounded-2xl p-3.5 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className={`w-7 h-7 rounded-lg inline-flex items-center justify-center shrink-0 ${online ? 'bg-emerald-400/10 text-emerald-300' : 'bg-white/[0.06] text-zinc-500'}`}>
            {icon}
          </span>
          <span className="text-[13px] font-medium text-white truncate">{name}</span>
        </div>
        <Badge tone={online ? 'emerald' : 'zinc'}>{status}</Badge>
      </div>
      {detail && <div className="text-[10px] font-mono text-zinc-600 uppercase tracking-wider">{detail}</div>}
      {progress !== undefined && <ProgressBar value={progress} tone="emerald" />}
    </div>
  );
}
