import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Server, KeyRound, Globe, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { GlassPanel } from '../ui/GlassPanel';
import { Button } from '../ui/Button';

interface SettingsSheetProps {
  open: boolean;
  onClose: () => void;
}

interface HealthState {
  status: 'checking' | 'online' | 'offline';
  latency?: number;
}

export function SettingsSheet({ open, onClose }: SettingsSheetProps) {
  const [health, setHealth] = useState<HealthState>({ status: 'checking' });
  const baseUrl = import.meta.env.VITE_API_URL || '';

  useEffect(() => {
    if (!open) return;
    let active = true;
    setHealth({ status: 'checking' });
    const start = performance.now();
    fetch(`${baseUrl}/health`)
      .then((res) => {
        if (!active) return;
        if (res.ok) {
          setHealth({ status: 'online', latency: Math.round(performance.now() - start) });
        } else {
          setHealth({ status: 'offline' });
        }
      })
      .catch(() => { if (active) setHealth({ status: 'offline' }); });
    return () => { active = false; };
  }, [open, baseUrl]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30 }}
            className="relative w-full max-w-md glass-strong rounded-3xl shadow-float overflow-hidden max-h-[90dvh]"
          >
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.07]">
              <h2 className="text-[15px] font-semibold text-white tracking-tight">Settings</h2>
              <button onClick={onClose} className="text-zinc-500 hover:text-white p-1" aria-label="Close">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4 overflow-y-auto thin-scrollbar">
              {/* Backend connection */}
              <GlassPanel tone="faint" className="p-4 flex items-start gap-3.5">
                <div className="w-9 h-9 rounded-xl bg-sky-400/10 text-sky-300 inline-flex items-center justify-center shrink-0">
                  <Server className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-white">API Gateway</div>
                  <div className="text-[11px] font-mono text-zinc-500 mt-0.5 break-all">{baseUrl}</div>
                </div>
                <div className="shrink-0">
                  {health.status === 'checking' && <Loader2 className="w-4 h-4 text-zinc-500 animate-spin" />}
                  {health.status === 'online' && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] text-emerald-300 font-medium">
                      <CheckCircle2 className="w-4 h-4" />
                      {health.latency} ms
                    </span>
                  )}
                  {health.status === 'offline' && (
                    <span className="inline-flex items-center gap-1.5 text-[11px] text-rose-300 font-medium">
                      <XCircle className="w-4 h-4" />
                      Offline
                    </span>
                  )}
                </div>
              </GlassPanel>

              {/* Access key */}
              <GlassPanel tone="faint" className="p-4 flex items-start gap-3.5">
                <div className="w-9 h-9 rounded-xl bg-violet-400/10 text-violet-300 inline-flex items-center justify-center shrink-0">
                  <KeyRound className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-white">Access Key</div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">
                    {import.meta.env.VITE_API_KEY ? 'Configured via VITE_API_KEY' : 'Not configured — set VITE_API_KEY to match the backend API_KEY'}
                  </div>
                </div>
              </GlassPanel>

              {/* Public URL */}
              <GlassPanel tone="faint" className="p-4 flex items-start gap-3.5">
                <div className="w-9 h-9 rounded-xl bg-emerald-400/10 text-emerald-300 inline-flex items-center justify-center shrink-0">
                  <Globe className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[13px] font-medium text-white">Public Access</div>
                  <div className="text-[11px] text-zinc-500 mt-0.5">
                    Expose this server with a stable Cloudflare URL via <span className="font-mono text-zinc-400">deployment/cloudflared_setup.sh</span>
                  </div>
                </div>
              </GlassPanel>
            </div>

            <div className="px-6 py-4 border-t border-white/[0.07] flex justify-end">
              <Button variant="secondary" onClick={onClose}>Done</Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
