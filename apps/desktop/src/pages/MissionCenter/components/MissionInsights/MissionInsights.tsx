import React, { useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Activity, AlertTriangle, ArrowRight, GitBranch, Gauge,
  FolderGit, ShieldCheck, Wrench, Lightbulb, RefreshCw,
} from 'lucide-react';
import { useWorkspaceStore } from '../../../../store/useWorkspaceStore';
import { useHealthStore, useMissionStore } from '../../store';

interface SuggestedAction {
  id: string;
  label: string;
  detail: string;
  tone: 'critical' | 'warn' | 'info';
  onClick?: () => void;
}

const toneStyles: Record<SuggestedAction['tone'], string> = {
  critical: 'border-rose-500/30 bg-rose-500/5 hover:bg-rose-500/10 text-rose-300',
  warn: 'border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 text-amber-300',
  info: 'border-cyan-border/30 bg-cyan-dim/5 hover:bg-cyan-dim/10 text-cyan-glow',
};

/**
 * MissionInsights — surfaces workspace health, a technical-debt summary and
 * suggested next actions. Reuses the existing Workspace Intelligence + Health
 * stores; introduces no new backend logic.
 */
export const MissionInsights: React.FC = () => {
  const { projects, insights, loadProjects, loadInsights, isOffline } = useWorkspaceStore();
  const services = useHealthStore((s) => s.services);
  const { missions, retryMission } = useMissionStore();

  useEffect(() => {
    if (projects.length === 0) loadProjects();
    loadInsights();
  }, [loadProjects, loadInsights, projects.length]);

  const healthy = services.filter((s) => s.status === 'HEALTHY').length;
  const degraded = services.filter((s) => s.status === 'WARNING').length;
  const down = services.filter((s) => s.status === 'ERROR' || s.status === 'OFFLINE').length;
  const healthPct = services.length ? Math.round((healthy / services.length) * 100) : 0;

  // Technical debt is derived from Workspace Intelligence graph stats + insights.
  const debt = useMemo(() => {
    const items: { label: string; severity: 'high' | 'medium' | 'low' }[] = [];
    for (const p of projects) {
      const stats = p.graph_stats;
      if (!stats) continue;
      if (stats.entry_points === 0) {
        items.push({ label: `${p.name}: no recognised entry point`, severity: 'medium' });
      }
      if (stats.total_files > 400) {
        items.push({ label: `${p.name}: ${stats.total_files} files — consider modularising`, severity: 'high' });
      } else if (stats.total_files > 150) {
        items.push({ label: `${p.name}: ${stats.total_files} files in one project`, severity: 'medium' });
      }
      if (stats.total_modules > 0 && stats.total_imports / Math.max(stats.total_modules, 1) > 25) {
        items.push({ label: `${p.name}: high coupling (${stats.total_imports} imports)`, severity: 'high' });
      }
    }
    // Fold in backend insights that read like warnings.
    for (const ins of insights?.insights ?? []) {
      if (/consider|no recognised|no entry/i.test(ins)) {
        items.push({ label: ins, severity: 'medium' });
      }
    }
    return items.slice(0, 6);
  }, [projects, insights]);

  const debtScore = useMemo(() => {
    const weight = debt.reduce((acc, d) => acc + (d.severity === 'high' ? 3 : d.severity === 'medium' ? 2 : 1), 0);
    return Math.min(100, weight * 8);
  }, [debt]);

  const suggestions = useMemo<SuggestedAction[]>(() => {
    const out: SuggestedAction[] = [];
    const failed = missions.find((m) => m.status === 'FAILED');
    if (failed) {
      out.push({
        id: `retry-${failed.id}`,
        label: `Retry "${failed.name}"`,
        detail: 'A mission failed — re-run it now.',
        tone: 'critical',
        onClick: () => retryMission(failed.id),
      });
    }
    if (down > 0) {
      out.push({
        id: 'health',
        label: `${down} subsystem${down > 1 ? 's' : ''} offline`,
        detail: 'Check kernel diagnostics and reconnect.',
        tone: 'warn',
      });
    }
    const unscanned = projects.find((p) => !p.graph_stats);
    if (unscanned) {
      out.push({
        id: 'scan',
        label: `Scan "${unscanned.name}"`,
        detail: 'Project not yet indexed by Workspace Intelligence.',
        tone: 'info',
        onClick: () => loadProjects(true),
      });
    }
    if (debtScore >= 40) {
      out.push({
        id: 'debt',
        label: 'Reduce technical debt',
        detail: `Debt index at ${debtScore}. Review flagged items.`,
        tone: 'warn',
      });
    }
    if (out.length === 0) {
      out.push({
        id: 'ok',
        label: 'Everything looks healthy',
        detail: 'No urgent actions detected.',
        tone: 'info',
      });
    }
    return out.slice(0, 4);
  }, [missions, down, projects, debtScore, retryMission, loadProjects]);

  return (
    <div className="space-y-4">
      {/* Workspace Health */}
      <div className="border border-matte-border/20 rounded-xl bg-matte-card/30 overflow-hidden">
        <div className="px-4 py-2.5 bg-black/10 flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-zinc-400 font-bold">
            <ShieldCheck className="w-3.5 h-3.5 text-cyan-glow" />
            Workspace Health
          </span>
          <span className={`text-[9px] font-mono font-bold ${healthPct >= 80 ? 'text-emerald-400' : healthPct >= 50 ? 'text-amber-400' : 'text-rose-400'}`}>
            {healthPct}%
          </span>
        </div>
        <div className="p-3.5 space-y-3">
          <div className="h-1.5 w-full bg-zinc-900 rounded-full overflow-hidden border border-matte-border">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${healthPct}%` }}
              transition={{ duration: 0.5 }}
              className={`h-full rounded-full ${healthPct >= 80 ? 'bg-emerald-400' : healthPct >= 50 ? 'bg-amber-400' : 'bg-rose-500'}`}
            />
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              { label: 'Healthy', value: healthy, cls: 'text-emerald-400', icon: Activity },
              { label: 'Degraded', value: degraded, cls: 'text-amber-400', icon: Gauge },
              { label: 'Down', value: down, cls: 'text-rose-400', icon: AlertTriangle },
            ].map((s) => (
              <div key={s.label} className="bg-black/20 border border-matte-border/40 rounded-lg py-2">
                <s.icon className={`w-3.5 h-3.5 mx-auto mb-1 ${s.cls}`} />
                <div className={`text-sm font-bold ${s.cls}`}>{s.value}</div>
                <div className="text-[8px] font-mono uppercase tracking-wider text-zinc-500">{s.label}</div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between text-[9px] font-mono text-zinc-500 pt-1 border-t border-matte-border/20">
            <span className="flex items-center gap-1"><FolderGit className="w-3 h-3" /> {projects.length} projects</span>
            <span className="flex items-center gap-1">
              <GitBranch className="w-3 h-3" />
              {projects.filter((p) => p.is_git).length} tracked
            </span>
          </div>
          {isOffline && (
            <p className="text-[9px] font-mono text-rose-400/80">Workspace API offline.</p>
          )}
        </div>
      </div>

      {/* Technical Debt Summary */}
      <div className="border border-matte-border/20 rounded-xl bg-matte-card/30 overflow-hidden">
        <div className="px-4 py-2.5 bg-black/10 flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-zinc-400 font-bold">
            <Wrench className="w-3.5 h-3.5 text-amber-400" />
            Technical Debt
          </span>
          <span className={`text-[9px] font-mono font-bold ${debtScore < 25 ? 'text-emerald-400' : debtScore < 60 ? 'text-amber-400' : 'text-rose-400'}`}>
            {debtScore < 25 ? 'LOW' : debtScore < 60 ? 'MODERATE' : 'HIGH'} · {debtScore}
          </span>
        </div>
        <div className="p-3.5 space-y-1.5">
          {debt.length === 0 ? (
            <p className="text-[9px] font-mono text-zinc-500">No significant debt detected.</p>
          ) : (
            debt.map((d, i) => (
              <div key={i} className="flex items-start gap-2 text-[9px] font-mono text-zinc-400 leading-relaxed">
                <span
                  className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                    d.severity === 'high' ? 'bg-rose-500' : d.severity === 'medium' ? 'bg-amber-400' : 'bg-zinc-600'
                  }`}
                />
                <span className="break-words">{d.label}</span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Suggested Next Actions */}
      <div className="border border-matte-border/20 rounded-xl bg-matte-card/30 overflow-hidden">
        <div className="px-4 py-2.5 bg-black/10 flex items-center gap-1.5 text-[9px] font-mono uppercase tracking-widest text-zinc-400 font-bold">
          <Lightbulb className="w-3.5 h-3.5 text-cyan-glow" />
          Suggested Next Actions
        </div>
        <div className="p-3 space-y-2">
          {suggestions.map((s) => {
            const Comp = s.onClick ? 'button' : 'div';
            return (
              <Comp
                key={s.id}
                onClick={s.onClick}
                className={`w-full text-left flex items-center gap-2.5 px-3 py-2 rounded-lg border transition-all ${toneStyles[s.tone]} ${s.onClick ? 'cursor-pointer' : ''}`}
              >
                <div className="flex-1 min-w-0">
                  <div className="text-[10px] font-bold truncate">{s.label}</div>
                  <div className="text-[8.5px] font-mono text-zinc-500 truncate">{s.detail}</div>
                </div>
                {s.onClick && (s.id.startsWith('scan') ? <RefreshCw className="w-3 h-3 shrink-0" /> : <ArrowRight className="w-3 h-3 shrink-0" />)}
              </Comp>
            );
          })}
        </div>
      </div>
    </div>
  );
};
