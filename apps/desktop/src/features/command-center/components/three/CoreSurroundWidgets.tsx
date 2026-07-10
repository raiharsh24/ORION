import React from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit, ListChecks, Database, Wrench } from 'lucide-react';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

const fmt = (n: number) => n.toLocaleString('en-US');

interface ChipProps {
  icon: React.ReactNode;
  value: string;
  label: string;
  accent: string;
  corner: string;
  glow?: boolean;
}

const StatChip: React.FC<ChipProps> = ({ icon, value, label, accent, corner, glow }) => (
  <div className={corner}>
    <motion.div
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
      className={`pointer-events-none relative flex flex-col items-center justify-center w-24 h-24 rounded-full border bg-black/45 backdrop-blur-md ${
        glow ? 'border-orange-glow/60 shadow-[0_0_18px_rgba(255,138,61,0.45)]' : 'border-cyan-border/40'
      } transition-shadow`}
    >
      <div className="absolute inset-1 rounded-full border border-cyan-border/20 cc-spin-slow" />
      <div className={`absolute inset-2 rounded-full border border-cyan-border/10 ${glow ? 'border-orange-glow/30' : ''}`} />
      <span className={`relative z-10 ${accent}`}>{icon}</span>
      <span className="relative z-10 text-base font-bold tabular-nums text-zinc-100 leading-tight mt-0.5">{value}</span>
      <span className="relative z-10 text-[7px] font-mono uppercase tracking-[0.15em] text-zinc-500">{label}</span>
    </motion.div>
  </div>
);

/**
 * Circular widgets surrounding the AI Core. Values stay synchronized with the
 * command-center store. "Tasks Running" brightens while the core is executing.
 */
export const CoreSurroundWidgets: React.FC = () => {
  const thoughts = useCommandCenterStore((s) => s.thoughtsProcessed);
  const tasks = useCommandCenterStore((s) => s.tasksRunning);
  const memories = useCommandCenterStore((s) => s.memoriesStored);
  const tools = useCommandCenterStore((s) => s.toolsAvailable);
  const executing = useCommandCenterStore((s) => s.coreState === 'executing' && !s.listening);

  return (
    <div className="absolute inset-0 pointer-events-none">
      <StatChip
        corner="absolute top-[15%] left-[10%]"
        icon={<BrainCircuit className="w-5 h-5" />}
        value={fmt(thoughts)}
        label="Thoughts"
        accent="text-cyan-glow"
      />
      <StatChip
        corner="absolute top-[15%] right-[10%]"
        icon={<ListChecks className="w-5 h-5" />}
        value={String(tasks)}
        label="Tasks"
        accent="text-orange-glow"
        glow={executing}
      />
      <StatChip
        corner="absolute bottom-[15%] left-[10%]"
        icon={<Database className="w-5 h-5" />}
        value={fmt(memories)}
        label="Memories"
        accent="text-cyan-glow"
      />
      <StatChip
        corner="absolute bottom-[15%] right-[10%]"
        icon={<Wrench className="w-5 h-5" />}
        value={String(tools)}
        label="Tools"
        accent="text-cyan-glow"
      />
    </div>
  );
};
