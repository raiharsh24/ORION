import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { useCognitiveStore } from './store';
import { useCognitiveEvents } from '../../services/realtime/hooks/useCognitiveEvents';
import { useRealtime } from '../../services/realtime/hooks/useRealtime';
import type { ConnectionState } from '../../services/realtime/streamManager';

import { MissionDashboard } from './components/MissionDashboard/MissionDashboard';
import { TimelineView } from './components/TimelineView/TimelineView';
import { GoalTree } from './components/GoalTree/GoalTree';
import { CognitivePanel } from './components/CognitivePanel/CognitivePanel';
import { MissionInspector } from './components/MissionInspector/MissionInspector';

import { LayoutDashboard, Timeline, Share2, BrainCircuit, Search } from 'lucide-react';

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'timeline', label: 'Timeline', icon: Timeline },
  { id: 'goaltree', label: 'Goal Tree', icon: Share2 },
  { id: 'cognitive', label: 'Cognitive Panel', icon: BrainCircuit },
  { id: 'inspector', label: 'Inspector', icon: Search },
] as const;

type TabId = (typeof TABS)[number]['id'];

export interface CognitiveDashboardPageProps {
  isLoading?: boolean;
  hasError?: boolean;
}

export const CognitiveDashboardPage: React.FC<CognitiveDashboardPageProps> = ({
  isLoading = false,
  hasError = false,
}) => {
  const [activeTab, setActiveTab] = useState<TabId>('dashboard');

  const {
    loadHealth, loadContext, loadGoals, loadReflections,
    loadScheduler, loadLearning,
  } = useCognitiveStore();

  const realtime = useRealtime();
  useCognitiveEvents();

  const [prevConnectionState, setPrevConnectionState] = useState<ConnectionState>('DISCONNECTED');

  useEffect(() => {
    if (realtime.connectionState === 'CONNECTED' && prevConnectionState !== 'CONNECTED') {
      loadHealth(); loadContext(); loadGoals(); loadReflections();
      loadScheduler(); loadLearning();
    }
    setPrevConnectionState(realtime.connectionState);
  }, [realtime.connectionState, prevConnectionState, loadHealth, loadContext, loadGoals, loadReflections, loadScheduler, loadLearning]);

  useEffect(() => {
    loadHealth(); loadContext(); loadGoals(); loadReflections();
    loadScheduler(); loadLearning();
  }, [loadHealth, loadContext, loadGoals, loadReflections, loadScheduler, loadLearning]);

  if (isLoading) {
    return (
      <div className="h-full bg-zinc-950 flex items-center justify-center text-zinc-400 font-mono text-xs gap-3 animate-pulse"
        aria-busy="true" aria-label="Loading Cognitive Dashboard"
      >
        <span className="w-2.5 h-2.5 rounded-full bg-cyan-glow animate-ping" />
        <span>Loading Cognitive Operating System Dashboard...</span>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="h-full bg-zinc-950 flex flex-col items-center justify-center text-center p-6 gap-3" role="alert">
        <span className="text-sm font-extrabold text-red-500 uppercase tracking-widest">Cognitive Dashboard Error</span>
        <p className="text-xs text-zinc-500 font-mono">Fatal crash loading dashboard shell boundaries.</p>
      </div>
    );
  }

  return (
    <motion.main
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col h-full bg-matte-card text-zinc-100 select-none overflow-hidden"
      role="main"
      aria-label="FRIDAY Cognitive Operating System Dashboard"
    >
      {/* Tab navigation */}
      <div className="flex border-b border-matte-border/30 bg-black/10 flex-shrink-0">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-5 py-3.5 text-[10px] font-mono uppercase tracking-widest border-r border-matte-border/20 focus:outline-none transition-colors
              ${activeTab === tab.id
                ? 'bg-cyan-dim/15 text-cyan-glow font-bold border-b-2 border-b-cyan-glow'
                : 'text-zinc-500 hover:text-zinc-300'
              }`}
            aria-pressed={activeTab === tab.id}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
        <div className="max-w-7xl mx-auto">
          {activeTab === 'dashboard' && <MissionDashboard />}
          {activeTab === 'timeline' && (
            <div className="max-w-3xl mx-auto">
              <TimelineView />
            </div>
          )}
          {activeTab === 'goaltree' && (
            <div className="max-w-3xl mx-auto">
              <GoalTree />
            </div>
          )}
          {activeTab === 'cognitive' && (
            <div className="max-w-2xl mx-auto">
              <CognitivePanel />
            </div>
          )}
          {activeTab === 'inspector' && (
            <div className="max-w-2xl mx-auto">
              <MissionInspector />
            </div>
          )}
        </div>
      </div>
    </motion.main>
  );
};
