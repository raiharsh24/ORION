import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FolderOpen, FileCode, ChevronRight, ChevronDown, Terminal, Database, FileText, Sparkles } from 'lucide-react';

export interface FileEntry {
  name: string;
  path: string;
  type: 'file' | 'directory';
  extension?: string;
  children?: FileEntry[];
  language?: string;
}

interface Props {
  files: FileEntry[];
  projectName: string;
  className?: string;
  /** Path of the currently active/focused file, highlighted in the tree. */
  activePath?: string;
  onFileClick?: (entry: FileEntry) => void;
  /** Optional secondary action rendered on hover (e.g. "Explain"). */
  onExplain?: (entry: FileEntry) => void;
}

const extIcon: Record<string, React.FC<{ className?: string }>> = {
  '.py': FileCode,
  '.ts': FileCode,
  '.tsx': FileCode,
  '.js': FileCode,
  '.jsx': FileCode,
  '.go': Terminal,
  '.rs': Terminal,
  '.json': Database,
  '.md': FileText,
  '.yml': FileText,
  '.yaml': FileText,
  '.toml': FileText,
};

function FileIcon({ entry }: { entry: FileEntry }) {
  if (entry.type === 'directory') return null;
  const ext = entry.extension || '';
  const Icon = extIcon[ext] || FileCode;
  return <Icon className="w-3.5 h-3.5 text-cyan-glow/70" />;
}

function TreeNode({
  entry,
  depth = 0,
  activePath,
  onFileClick,
  onExplain,
}: {
  entry: FileEntry;
  depth?: number;
  activePath?: string;
  onFileClick?: (entry: FileEntry) => void;
  onExplain?: (entry: FileEntry) => void;
}) {
  const [open, setOpen] = useState(depth < 1);
  const isDir = entry.type === 'directory';
  const isActive = !!activePath && entry.path === activePath;

  return (
    <div>
      <div
        className={`group w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs transition-all
          ${isActive
            ? 'bg-cyan-dim/20 border border-cyan-border/40 text-cyan-glow shadow-[0_0_10px_rgba(0,242,254,0.05)]'
            : isDir
              ? 'text-zinc-300 hover:bg-zinc-900/60 border border-transparent'
              : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/40 border border-transparent'
          }`}
      >
        <button
          type="button"
          onClick={() => {
            if (isDir) setOpen(!open);
            onFileClick?.(entry);
          }}
          className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer text-left"
        >
          {isDir ? (
            <span className="text-zinc-500 shrink-0">
              {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </span>
          ) : (
            <span className="w-3.5 shrink-0" />
          )}

          {isDir ? (
            <FolderOpen className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-cyan-glow' : 'text-amber-400/80'}`} />
          ) : (
            <FileIcon entry={entry} />
          )}

          <span className="truncate">{entry.name}</span>

          {isActive && (
            <span className="ml-1 text-[8px] font-mono uppercase tracking-widest text-cyan-glow/80 shrink-0">active</span>
          )}

          {entry.language && !isActive && (
            <span className="ml-auto text-[9px] font-mono text-zinc-600 uppercase">{entry.language}</span>
          )}
        </button>

        {onExplain && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onExplain(entry);
            }}
            title={`Explain ${entry.name}`}
            className="shrink-0 opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded-md text-zinc-500 hover:text-cyan-glow hover:bg-cyan-dim/10 transition-all"
          >
            <Sparkles className="w-3 h-3" />
          </button>
        )}
      </div>

      <AnimatePresence initial={false}>
        {isDir && open && entry.children && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="overflow-hidden"
          >
            <div className="ml-3 border-l border-matte-border/40 pl-1">
              {entry.children.map((child) => (
                <TreeNode
                  key={child.path}
                  entry={child}
                  depth={depth + 1}
                  activePath={activePath}
                  onFileClick={onFileClick}
                  onExplain={onExplain}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export const WorkspaceMiniGraph: React.FC<Props> = ({
  files,
  projectName,
  className = '',
  activePath,
  onFileClick,
  onExplain,
}) => {
  return (
    <div className={`${className}`}>
      {files.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-zinc-500">
          <FolderOpen className="w-8 h-8 mb-2 opacity-30" />
          <p className="text-xs font-mono">No files scanned in {projectName}</p>
        </div>
      ) : (
        <div className="space-y-0.5">
          {files.map((entry) => (
            <TreeNode
              key={entry.path}
              entry={entry}
              activePath={activePath}
              onFileClick={onFileClick}
              onExplain={onExplain}
            />
          ))}
        </div>
      )}
    </div>
  );
};
