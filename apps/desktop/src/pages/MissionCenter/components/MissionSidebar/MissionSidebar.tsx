import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Pin, ClipboardList, AlertCircle, Loader } from 'lucide-react';
import { useMissionStore } from '../../store';
import { MissionCard } from '../MissionCard/MissionCard';

// 1. TypeScript interface for Props
export interface MissionSidebarProps {
  isLoading?: boolean;
  hasError?: boolean;
}

// 2. Export component
export const MissionSidebar: React.FC<MissionSidebarProps> = ({
  isLoading = false,
  hasError = false,
}) => {
  const { 
    missions, 
    sidebarFilter, 
    setFilter, 
    selectMission, 
    activeMissionId,
    searchQuery,
    setSearch,
    pinnedMissions,
    togglePin
  } = useMissionStore();

  // 3. Accessibility comments
  // role="navigation" helps accessibility screen readers classify the layout
  // aria-busy indicates async fetching sequences

  // 4. Loading placeholder
  if (isLoading) {
    return (
      <div 
        className="w-80 border-r border-matte-border/30 bg-black/20 p-4 space-y-4"
        aria-busy="true"
        aria-label="Loading missions list"
      >
        <div className="flex items-center gap-2 text-zinc-500 font-mono text-[10px]">
          <Loader className="w-3.5 h-3.5 animate-spin text-cyan-glow" />
          <span>Synchronizing...</span>
        </div>
        {[1, 2, 3].map((n) => (
          <div key={n} className="h-24 bg-zinc-850 animate-pulse rounded-xl" />
        ))}
      </div>
    );
  }

  // 5. Error state
  if (hasError) {
    return (
      <div 
        className="w-80 border-r border-matte-border/30 bg-red-950/20 p-6 flex flex-col justify-center items-center text-center gap-2"
        role="alert"
      >
        <AlertCircle className="w-6 h-6 text-red-400" />
        <span className="text-xs font-bold text-red-400 uppercase tracking-wider">Sync Failure</span>
        <p className="text-[10px] text-zinc-500 font-mono">Failed to fetch active mission metrics.</p>
      </div>
    );
  }

  // Filter list by category and search term
  const searchedMissions = missions.filter((m) => {
    const matchSearch = m.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                        m.description.toLowerCase().includes(searchQuery.toLowerCase());
    if (!matchSearch) return false;
    
    if (sidebarFilter === 'all') return true;
    return m.status.toLowerCase() === sidebarFilter.toLowerCase();
  });

  const pinnedList = searchedMissions.filter((m) => pinnedMissions.includes(m.id));
  const unpinnedList = searchedMissions.filter((m) => !pinnedMissions.includes(m.id));

  return (
    <aside 
      className="w-80 border-r border-matte-border/30 bg-black/25 flex flex-col h-full overflow-hidden"
      role="navigation"
      aria-label="Missions Sidebar Panel"
    >
      {/* Sidebar Header */}
      <div className="p-4.5 border-b border-matte-border/20 flex flex-col gap-3.5">
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <ClipboardList className="w-4 h-4 text-cyan-glow" />
            <h2 className="text-xs font-extrabold text-zinc-200 tracking-wider uppercase font-mono">
              Mission Registry
            </h2>
          </div>
          <span className="text-[8px] font-mono px-2 py-0.5 rounded-full bg-cyan-dim/40 text-cyan-glow border border-cyan-border/25 font-bold">
            {searchedMissions.length} items
          </span>
        </div>

        {/* Search bar */}
        <div className="relative">
          <Search className="absolute left-3 top-2.5 w-3.5 h-3.5 text-zinc-500" />
          <input
            type="text"
            placeholder="Search missions..."
            value={searchQuery}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-zinc-950/80 border border-matte-border/25 focus:border-cyan-glow/40 rounded-lg text-[11px] font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none transition-colors"
            aria-label="Search missions by keywords"
          />
        </div>

        {/* Category switcher */}
        <div className="grid grid-cols-4 gap-1 bg-zinc-950/50 p-0.5 rounded-lg border border-matte-border/20">
          {(['all', 'running', 'completed', 'failed'] as const).map((filterOpt) => (
            <button
              key={filterOpt}
              onClick={() => setFilter(filterOpt)}
              className={`py-1 rounded text-[9px] font-mono uppercase tracking-wider transition-colors focus:outline-none
                ${sidebarFilter === filterOpt 
                  ? 'bg-cyan-dim/15 text-cyan-glow font-bold' 
                  : 'text-zinc-500 hover:text-zinc-300'
                }
              `}
              aria-pressed={sidebarFilter === filterOpt}
            >
              {filterOpt}
            </button>
          ))}
        </div>
      </div>

      {/* 6. Empty State */}
      {searchedMissions.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-6 text-zinc-500 gap-2">
          <ClipboardList className="w-5 h-5 text-zinc-650" />
          <span className="text-xs font-mono tracking-wider">No Missions Found</span>
          <p className="text-[10px] text-zinc-600 font-mono max-w-[200px]">
            Try adjusting search terms or status filter.
          </p>
        </div>
      ) : (
        /* Scroller lists */
        <div className="flex-1 overflow-y-auto p-4 space-y-4.5 scrollbar-thin">
          <AnimatePresence mode="popLayout">
            {/* Pinned list */}
            {pinnedList.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-[8px] font-mono uppercase tracking-widest text-zinc-500 pb-1 border-b border-matte-border/10">
                  <Pin className="w-2.5 h-2.5 text-cyan-glow" />
                  <span>Pinned</span>
                </div>
                {pinnedList.map((m) => (
                  <motion.div
                    key={m.id}
                    layout
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    transition={{ duration: 0.2 }}
                  >
                    <MissionCard
                      mission={m}
                      isActive={activeMissionId === m.id}
                      isPinned={true}
                      onClick={() => selectMission(m.id)}
                      onTogglePin={(e) => {
                        e.stopPropagation();
                        togglePin(m.id);
                      }}
                    />
                  </motion.div>
                ))}
              </div>
            )}

            {/* General/Unpinned list */}
            <div className="space-y-2">
              {pinnedList.length > 0 && unpinnedList.length > 0 && (
                <div className="text-[8px] font-mono uppercase tracking-widest text-zinc-600 pb-1 border-b border-matte-border/10">
                  Active Registry
                </div>
              )}
              {unpinnedList.map((m) => (
                <motion.div
                  key={m.id}
                  layout
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  transition={{ duration: 0.2 }}
                >
                  <MissionCard
                    mission={m}
                    isActive={activeMissionId === m.id}
                    isPinned={false}
                    onClick={() => selectMission(m.id)}
                    onTogglePin={(e) => {
                      e.stopPropagation();
                      togglePin(m.id);
                    }}
                  />
                </motion.div>
              ))}
            </div>
          </AnimatePresence>
        </div>
      )}
    </aside>
  );
};
