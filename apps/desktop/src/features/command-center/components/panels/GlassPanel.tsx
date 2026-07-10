import React from 'react';
import { motion } from 'framer-motion';
import { LiveIndicator } from '../widgets/LiveIndicator';

interface GlassPanelProps {
  title?: string;
  icon?: React.ReactNode;
  live?: boolean;
  liveColor?: 'cyan' | 'orange' | 'green';
  action?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  breathe?: boolean;
  sweep?: boolean;
  children: React.ReactNode;
}

/**
 * Reusable frosted-glass HUD panel. Every Command Center widget is built on this
 * so borders, glow, spacing and the LIVE indicator stay consistent.
 */
export const GlassPanel: React.FC<GlassPanelProps> = ({
  title,
  icon,
  live = false,
  liveColor = 'cyan',
  action,
  className = '',
  bodyClassName = '',
  breathe = true,
  sweep = false,
  children,
}) => (
  <motion.section
    initial={{ opacity: 0, y: 12 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ duration: 0.4, ease: 'easeOut' }}
    className={`relative overflow-hidden cc-glass cc-glass-hover ${breathe ? 'cc-breathe' : ''} ${sweep ? 'cc-sweep' : ''} ${className}`}
  >
    {(title || live || action) && (
      <header className="flex items-center justify-between px-4 pt-3 pb-2.5">
        <div className="flex items-center gap-2 min-w-0">
          {icon && <span className="text-cyan-glow/80 shrink-0">{icon}</span>}
          {title && (
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-zinc-300 truncate">
              {title}
            </h3>
          )}
        </div>
        <div className="flex items-center gap-3 shrink-0">
          {action}
          {live && <LiveIndicator color={liveColor} />}
        </div>
      </header>
    )}
    <div className={`px-4 pb-4 ${title ? '' : 'pt-4'} ${bodyClassName}`}>{children}</div>
  </motion.section>
);
