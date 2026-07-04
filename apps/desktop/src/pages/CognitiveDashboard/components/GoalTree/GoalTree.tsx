import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardHeader, CardTitle, CardContent } from '../../../../components/ui/Card';
import { useCognitiveStore } from '../../store';
import { ChevronRight, ChevronDown, Milestone, CheckCircle2, Circle } from 'lucide-react';

interface TreeNodeProps {
  nodeId: string;
  objective: string;
  status: string;
  progress: number;
  children: string[];
  allNodes: Map<string, CognitiveNode>;
  depth: number;
}

interface CognitiveNode {
  goal_id: string;
  objective: string;
  parent_id: string | null;
  children: string[];
  status: string;
  priority: number;
  progress_pct: number;
  depends_on: string[];
  milestones: number;
}

const statusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'text-emerald-400 border-emerald-400/30';
    case 'failed': return 'text-red-400 border-red-400/30';
    case 'active': return 'text-cyan-glow border-cyan-border/50';
    default: return 'text-zinc-500 border-matte-border/30';
  }
};

const TreeNode: React.FC<TreeNodeProps> = ({ nodeId: _nodeId, objective, status, progress, children, allNodes, depth }) => {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = children.length > 0;

  return (
    <div>
      <div
        className={`
          flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer
          transition-colors hover:bg-white/5 group
          ${statusColor(status)}
        `}
        style={{ marginLeft: depth * 20 }}
        onClick={() => hasChildren && setExpanded(!expanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); hasChildren && setExpanded(!expanded); } }}
        aria-expanded={hasChildren ? expanded : undefined}
      >
        {hasChildren ? (
          expanded ? <ChevronDown className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" /> : <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 text-zinc-500" />
        ) : (
          <span className="w-3.5 h-3.5 flex-shrink-0" />
        )}

        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
          status === 'completed' ? 'bg-emerald-400' :
          status === 'failed' ? 'bg-red-400' :
          status === 'active' ? 'bg-cyan-glow' :
          'bg-zinc-600'
        }`} />

        <span className="text-xs font-mono text-zinc-300 truncate flex-1">{objective}</span>

        <span className="text-[8px] font-mono uppercase text-zinc-600 flex-shrink-0 px-1.5 py-0.5 rounded border border-matte-border/20">
          {status}
        </span>

        <div className="w-12 h-1 rounded-full bg-zinc-800 overflow-hidden flex-shrink-0">
          <div
            className="h-full rounded-full bg-cyan-glow transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="text-[9px] font-mono text-zinc-500 w-7 text-right flex-shrink-0">
          {Math.round(progress)}%
        </span>
      </div>

      <AnimatePresence>
        {hasChildren && expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
          >
            {children.map((childId) => {
              const child = allNodes.get(childId);
              if (!child) return null;
              return (
                <TreeNode
                  key={childId}
                  nodeId={childId}
                  objective={child.objective}
                  status={child.status}
                  progress={child.progress_pct}
                  children={child.children}
                  allNodes={allNodes}
                  depth={depth + 1}
                />
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export const GoalTree: React.FC = () => {
  const { goals, hierarchyNodes, activeGoal } = useCognitiveStore();

  const nodes = hierarchyNodes.length > 0 ? hierarchyNodes : goals.map((g) => ({
    goal_id: g.goal_id,
    objective: g.objective,
    parent_id: g.parent_id,
    children: [],
    status: g.status,
    priority: g.priority,
    progress_pct: g.progress_pct,
    depends_on: [],
    milestones: g.milestones,
  }));

  const nodeMap = new Map<string, CognitiveNode>();
  nodes.forEach((n) => nodeMap.set(n.goal_id, n));

  const roots = nodes.filter((n) => !n.parent_id);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Goal Hierarchy Tree</CardTitle>
      </CardHeader>
      <CardContent>
        {roots.length === 0 ? (
          <div className="text-xs text-zinc-600 font-mono py-8 text-center">
            No goals in hierarchy. Create goals to see them here.
          </div>
        ) : (
          <div className="space-y-1">
            {roots.map((root) => (
              <TreeNode
                key={root.goal_id}
                nodeId={root.goal_id}
                objective={root.objective}
                status={root.status}
                progress={root.progress_pct}
                children={root.children}
                allNodes={nodeMap}
                depth={0}
              />
            ))}
          </div>
        )}

        {activeGoal && activeGoal.milestones.length > 0 && (
          <div className="mt-6 pt-4 border-t border-matte-border/20">
            <div className="flex items-center gap-2 mb-3">
              <Milestone className="w-3.5 h-3.5 text-cyan-glow" />
              <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">
                Milestones — {activeGoal.objective.slice(0, 40)}
              </span>
            </div>
            <div className="space-y-1.5">
              {activeGoal.milestones.map((ms) => (
                <div key={ms.id} className="flex items-center gap-3 px-3 py-1.5">
                  {ms.completed ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
                  ) : (
                    <Circle className="w-3.5 h-3.5 text-zinc-600 flex-shrink-0" />
                  )}
                  <span className={`text-xs font-mono ${ms.completed ? 'text-zinc-300 line-through opacity-60' : 'text-zinc-400'}`}>
                    {ms.name}
                  </span>
                  {ms.completed_at && (
                    <span className="text-[8px] font-mono text-zinc-600 ml-auto">
                      {new Date(ms.completed_at * 1000).toLocaleDateString()}
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
