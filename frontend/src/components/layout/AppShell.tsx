import { useCallback, useEffect, useState, lazy, Suspense } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X, WifiOff, RefreshCw } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { RightPanel } from './RightPanel';
import { MobileTabBar } from './MobileTabBar';
import { ChatView } from '../chat/ChatView';
import { SplashScreen } from './SplashScreen';
import { SettingsSheet } from '../settings/SettingsSheet';
import { Sheet } from '../ui/Sheet';
import { IconButton } from '../ui/IconButton';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { useTelemetry } from '../../hooks/useTelemetry';
import type { ModuleId } from '../../types';

const MiningIntelView = lazy(() =>
  import('../modules/MiningIntelView').then((m) => ({ default: m.MiningIntelView })),
);
const FinanceView = lazy(() =>
  import('../modules/FinanceView').then((m) => ({ default: m.FinanceView })),
);
const TaskView = lazy(() =>
  import('../modules/TaskView').then((m) => ({ default: m.TaskView })),
);
const KnowledgeView = lazy(() =>
  import('../modules/KnowledgeView').then((m) => ({ default: m.KnowledgeView })),
);

const MODULE_TITLES: Record<ModuleId, string> = {
  chat: 'Command',
  intel: 'Mining Intelligence',
  finance: 'Finance Engine',
  tasks: 'Operations',
  knowledge: 'Knowledge Base',
};

const BOOT_URL = import.meta.env.VITE_API_URL || '';

export function AppShell() {
  const [activeModule, setActiveModule] = useState<ModuleId>('chat');
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [telemetryOpen, setTelemetryOpen] = useState(false);
  const [sessionRefreshKey, setSessionRefreshKey] = useState(0);
  const [booting, setBooting] = useState(true);
  const [bootRetry, setBootRetry] = useState(0);

  const { data: telemetry, error: telemetryError, refresh } = useTelemetry(10_000);
  const online = !telemetryError && !!telemetry;

  // Boot gate: wait for a backend health signal (or 2.2s timeout) then fade the splash.
  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => { if (active) setBooting(false); }, 2200);
    fetch(`${BOOT_URL}/health`)
      .then((res) => {
        if (active && res.ok) {
          window.clearTimeout(timer);
          window.setTimeout(() => { if (active) setBooting(false); }, 700);
        }
      })
      .catch(() => { /* backend offline — proceed so offline states can guide the user */ });
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [bootRetry]);

  const handleNewSession = useCallback(() => {
    setActiveModule('chat');
    setActiveSessionId(null);
    setNavOpen(false);
  }, []);

  const handleSelectModule = useCallback((m: ModuleId) => {
    setActiveModule(m);
    setNavOpen(false);
  }, []);

  const handleSelectSession = useCallback((id: string) => {
    setActiveModule('chat');
    setActiveSessionId(id);
    setNavOpen(false);
  }, []);

  const handleActivity = useCallback(() => {
    setSessionRefreshKey((k) => k + 1);
  }, []);

  const handleReconnect = useCallback(() => {
    setBootRetry((r) => r + 1);
    void refresh();
  }, [refresh]);

  return (
    <div className="h-full w-full flex app-aurora app-grain relative overflow-hidden">
      <AnimatePresence>
        {booting && <SplashScreen ready={online} />}
      </AnimatePresence>

      {/* Aurora blobs */}
      <div className="aurora-blob w-[420px] h-[420px] -top-32 -left-24 bg-sky-600/40" />
      <div className="aurora-blob w-[380px] h-[380px] top-1/3 -right-24 bg-violet-600/40" style={{ animationDelay: '-8s' }} />

      {/* Settings */}
      <SettingsSheet open={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {/* Mobile nav (left) */}
      <Sheet open={navOpen} onClose={() => setNavOpen(false)} side="left" width="w-[320px]">
        <Sidebar
          activeModule={activeModule}
          activeSessionId={activeSessionId}
          onSelectModule={handleSelectModule}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onOpenSettings={() => { setSettingsOpen(true); setNavOpen(false); }}
          sessionRefreshKey={sessionRefreshKey}
        />
      </Sheet>

      {/* Mobile telemetry (right) */}
      <Sheet open={telemetryOpen} onClose={() => setTelemetryOpen(false)} side="right" width="w-[340px]">
        <div className="relative h-full">
          <div className="absolute top-3 right-3 z-10">
            <IconButton label="Close telemetry" onClick={() => setTelemetryOpen(false)}>
              <X className="w-5 h-5" />
            </IconButton>
          </div>
          <RightPanel className="w-full border-none" />
        </div>
      </Sheet>

      {/* Desktop sidebar */}
      <div className="hidden lg:flex">
        <Sidebar
          activeModule={activeModule}
          activeSessionId={activeSessionId}
          onSelectModule={handleSelectModule}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onOpenSettings={() => setSettingsOpen(true)}
          sessionRefreshKey={sessionRefreshKey}
        />
      </div>

      {/* Main canvas. pb-24 on mobile reserves room for the floating tab bar so
          the chat composer and module content never sit underneath it. */}
      <main className="flex-1 min-w-0 h-full relative z-10 flex flex-col pb-24 md:pb-0">
        <TopBar
          title={MODULE_TITLES[activeModule]}
          online={online}
          onToggleNav={() => setNavOpen(true)}
          onToggleTelemetry={() => setTelemetryOpen(true)}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        {!online && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            className="overflow-hidden border-b border-white/[0.06]"
          >
            <div className="flex items-center justify-between gap-3 px-4 md:px-6 py-2.5 bg-gradient-to-r from-rose-500/[0.08] to-transparent">
              <div className="flex items-center gap-2.5 text-[13px] text-rose-200/90 min-w-0">
                <WifiOff className="w-4 h-4 shrink-0" />
                <span className="truncate">
                  Backend unreachable at <span className="font-mono">{BOOT_URL}</span>
                </span>
              </div>
              <Button variant="secondary" size="sm" onClick={handleReconnect}>
                <RefreshCw className="w-3.5 h-3.5" />
                Retry
              </Button>
            </div>
          </motion.div>
        )}

        <div className="flex-1 min-h-0 relative">
          <AnimatePresence mode="wait">
            <motion.div
              key={activeModule}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
              className="h-full"
            >
              {activeModule === 'chat' && (
                <ChatView
                  activeSessionId={activeSessionId}
                  onSessionCreated={setActiveSessionId}
                  onActivity={handleActivity}
                />
              )}
              <Suspense
                fallback={
                  <div className="h-full flex items-center justify-center text-sky-300">
                    <Spinner className="w-6 h-6" />
                  </div>
                }
              >
                {activeModule === 'intel' && <MiningIntelView />}
                {activeModule === 'finance' && <FinanceView />}
                {activeModule === 'tasks' && <TaskView />}
                {activeModule === 'knowledge' && <KnowledgeView />}
              </Suspense>
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Desktop telemetry */}
      <div className="hidden xl:block relative z-10">
        <RightPanel />
      </div>

      {/* Mobile tab bar */}
      <MobileTabBar activeModule={activeModule} onSelectModule={handleSelectModule} />
    </div>
  );
}
