import React from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit, ListChecks, Database, Wrench } from 'lucide-react';
import { useCommandCenterStore } from '../../store/useCommandCenterStore';

const fmt = (n: number) => n.toLocaleString('en-US');

interface ChipProps {
  icon: React.ReactNode;
  value: string;
  label: string;
  sublabel: string;
  accent: string;
  corner: string;
  glow?: boolean;
  floatDelay: number;
  floatDuration: number;
}

const StatChip: React.FC<ChipProps> = ({ 
  icon, value, label, sublabel, accent, corner, glow, floatDelay, floatDuration 
}) => (
  <div className={corner}>
    <motion.div
      initial={{ opacity: 0, scale: 0.7 }}
      animate={{ 
        opacity: 1, 
        scale: 1,
        y: [0, -6, 0, 6, 0],
        x: [0, 3, 0, -3, 0]
      }}
      transition={{
        scale: { duration: 0.5, ease: 'easeOut' },
        opacity: { duration: 0.5, ease: 'easeOut' },
        y: { duration: floatDuration, repeat: Infinity, ease: 'easeInOut', delay: floatDelay },
        x: { duration: floatDuration * 1.2, repeat: Infinity, ease: 'easeInOut', delay: floatDelay * 0.5 }
      }}
      className={`pointer-events-none relative flex flex-col items-center justify-center w-26 h-26 rounded-full border bg-black/55 backdrop-blur-md transition-shadow ${
        glow 
          ? 'border-orange-glow/65 shadow-[0_0_20px_rgba(255,138,61,0.45)]' 
          : 'border-cyan-border/35 shadow-[0_0_15px_rgba(0,242,254,0.1)]'
      }`}
    >
      {/* HUD Spinners */}
      <div className="absolute inset-1 rounded-full border border-cyan-border/20 cc-spin-slow" />
      <div className={`absolute inset-2.5 rounded-full border border-dashed border-cyan-border/10 ${glow ? 'border-orange-glow/20' : ''}`} />
      
      {/* Mini-icon */}
      <span className={`relative z-10 opacity-70 ${accent}`}>{icon}</span>
      
      {/* Label (Top) */}
      <span className="relative z-10 text-[7px] font-mono uppercase tracking-[0.18em] text-zinc-500 leading-none mt-1">
        {label}
      </span>
      
      {/* Large Value (Center) */}
      <span className="relative z-10 text-sm font-black tabular-nums text-zinc-100 leading-tight my-0.5 cc-text-glow">
        {value}
      </span>
      
      {/* Sublabel (Bottom) */}
      <span className="relative z-10 text-[6.5px] font-mono uppercase tracking-[0.12em] text-zinc-400">
        {sublabel}
      </span>
    </motion.div>
  </div>
);

/**
 * Orbiting HUD widgets surrounding the AI Core.
 * Floating transitions added to matches the target design.
 */
export const CoreSurroundWidgets: React.FC = () => {
  const thoughts = useCommandCenterStore((s) => s.thoughtsProcessed);
  const tasks = useCommandCenterStore((s) => s.tasksRunning);
  const memories = useCommandCenterStore((s) => s.memoriesStored);
  const tools = useCommandCenterStore((s) => s.toolsAvailable);
  const executing = useCommandCenterStore((s) => s.coreState === 'executing' && !s.listening);

  return (
    <div className="absolute inset-0 pointer-events-none">
      {/* Left side widgets */}
      <StatChip
        corner="absolute top-[32%] left-[12%]"
        icon={<BrainCircuit className="w-3.5 h-3.5" />}
        value={fmt(thoughts)}
        label="Thoughts"
        sublabel="Processed"
        accent="text-cyan-glow"
        floatDelay={0}
        floatDuration={6.5}
      />
      <StatChip
        corner="absolute bottom-[22%] left-[12%]"
        icon={<ListChecks className="w-3.5 h-3.5" />}
        value={String(tasks)}
        label="Tasks"
        sublabel="Running"
        accent="text-orange-glow"
        glow={executing}
        floatDelay={1.5}
        floatDuration={7.2}
      />

      {/* Right side widgets */}
      <StatChip
        corner="absolute top-[32%] right-[12%]"
        icon={<Database className="w-3.5 h-3.5" />}
        value={fmt(memories)}
        label="Memories"
        sublabel="Stored"
        accent="text-cyan-glow"
        floatDelay={0.8}
        floatDuration={8.0}
      />
      <StatChip
        corner="absolute bottom-[22%] right-[12%]"
        icon={<Wrench className="w-3.5 h-3.5" />}
        value={String(tools)}
        label="Tools"
        sublabel="Available"
        accent="text-cyan-glow"
        floatDelay={2.2}
        floatDuration={6.8}
      />
    </div>
  );
};
export default CoreSurroundWidgets;
