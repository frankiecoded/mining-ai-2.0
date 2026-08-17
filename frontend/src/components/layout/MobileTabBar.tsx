import type { ComponentType } from 'react';
import { motion } from 'framer-motion';
import { MessageSquare, Map, Landmark, FolderKanban, Database } from 'lucide-react';
import type { ModuleId } from '../../types';

const TABS: Array<{ id: ModuleId; label: string; icon: ComponentType<{ className?: string }> }> = [
  { id: 'chat', label: 'Chat', icon: MessageSquare },
  { id: 'intel', label: 'Intel', icon: Map },
  { id: 'finance', label: 'Finance', icon: Landmark },
  { id: 'tasks', label: 'Ops', icon: FolderKanban },
  { id: 'knowledge', label: 'Know', icon: Database },
];

export function MobileTabBar({
  activeModule,
  onSelectModule,
}: {
  activeModule: ModuleId;
  onSelectModule: (m: ModuleId) => void;
}) {
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 pb-safe">
      <div className="mx-4 mb-3 glass-strong rounded-3xl px-2 py-2 flex items-center justify-between shadow-float">
        {TABS.map((tab) => {
          const active = activeModule === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectModule(tab.id)}
              aria-label={tab.label}
              className={`relative flex flex-col items-center justify-center flex-1 py-1 rounded-2xl transition-colors duration-200 ${
                active ? 'text-white' : 'text-zinc-500'
              }`}
            >
              {active && (
                <motion.span
                  layoutId="mobile-tab-active"
                  className="absolute inset-0 rounded-2xl bg-white/[0.1]"
                  transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                />
              )}
              <tab.icon className="w-[21px] h-[21px] relative z-10" />
              <span className="relative z-10 text-[10px] font-medium mt-0.5">{tab.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
