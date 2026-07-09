import React, { useEffect, useRef, useState } from 'react';
import { Search, X, CornerDownLeft } from 'lucide-react';
import { useKnowledgeStore } from '../store/useKnowledgeStore';
import type { GraphNode } from '../types';

export const SearchBar: React.FC = () => {
  const { searchQuery, setSearchQuery, searchResults, setSelectedNodeId } = useKnowledgeStore();
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Focus input when user presses '/' key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === '/' && document.activeElement !== inputRef.current) {
        e.preventDefault();
        inputRef.current?.focus();
        setDropdownOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Close search dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectNode = (node: GraphNode) => {
    setSelectedNodeId(node.id);
    setSearchQuery('');
    setDropdownOpen(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (searchResults.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % searchResults.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + searchResults.length) % searchResults.length);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const node = searchResults[selectedIndex];
      if (node) {
        handleSelectNode(node);
      }
    } else if (e.key === 'Escape') {
      setDropdownOpen(false);
      inputRef.current?.blur();
    }
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-sm z-30">
      <div className="relative">
        <div className="absolute inset-y-0 left-3.5 flex items-center pointer-events-none">
          <Search className="h-4 w-4 text-zinc-500" />
        </div>
        <input
          ref={inputRef}
          type="text"
          value={searchQuery}
          onChange={(e) => {
            setSearchQuery(e.target.value);
            setDropdownOpen(true);
            setSelectedIndex(0);
          }}
          onFocus={() => setDropdownOpen(true)}
          onKeyDown={handleKeyDown}
          placeholder="Search subsystems (Press '/' to focus)..."
          className="w-full bg-black/60 border border-matte-border hover:border-cyan-border/20 focus:border-cyan-glow/50 text-zinc-200 placeholder-zinc-500 text-xs font-mono rounded-xl pl-10 pr-9 py-2.5 outline-none transition-all duration-200"
        />
        {searchQuery ? (
          <button
            onClick={() => {
              setSearchQuery('');
              setDropdownOpen(false);
            }}
            className="absolute inset-y-0 right-3 flex items-center text-zinc-500 hover:text-zinc-300 focus:outline-none transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        ) : (
          <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none">
            <kbd className="font-mono text-[9px] text-zinc-600 bg-zinc-950 px-1.5 py-0.5 rounded border border-matte-border/30">
              /
            </kbd>
          </div>
        )}
      </div>

      {/* Fuzzy search virtualized results dropdown */}
      {dropdownOpen && searchQuery && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-black/90 border border-matte-border/55 backdrop-blur-md rounded-xl max-h-72 overflow-y-auto scrollbar-thin shadow-2xl p-1.5 space-y-0.5">
          {searchResults.length === 0 ? (
            <div className="py-8 text-center text-zinc-600 font-mono text-[10px] uppercase">
              No matching nodes found
            </div>
          ) : (
            searchResults.slice(0, 50).map((node, idx) => {
              const isSelected = selectedIndex === idx;
              return (
                <div
                  key={node.id}
                  onClick={() => handleSelectNode(node)}
                  className={`w-full flex items-start justify-between px-3 py-2 rounded-lg font-mono text-[10px] text-left transition-all duration-150 cursor-pointer select-none
                    ${isSelected
                      ? 'bg-cyan-dim/15 border-l-2 border-cyan-glow text-zinc-100 shadow-[0_0_10px_rgba(0,242,254,0.03)]'
                      : 'hover:bg-zinc-900/40 text-zinc-400'
                    }
                  `}
                >
                  <div className="space-y-0.5 max-w-[85%]">
                    <div className="flex items-center gap-1.5">
                      <span className="font-bold text-zinc-200 group-hover:text-cyan-glow truncate">
                        {node.title}
                      </span>
                      <span className="text-[7.5px] border px-1 rounded uppercase tracking-wider text-[8px] bg-zinc-900 border-zinc-800 scale-90">
                        {node.type}
                      </span>
                    </div>
                    <p className="text-[8.5px] text-zinc-500 truncate leading-relaxed">
                      {node.description}
                    </p>
                  </div>
                  {isSelected && (
                    <span className="text-[7.5px] text-cyan-glow/60 flex items-center gap-0.5 pr-1 pt-1.5">
                      <CornerDownLeft className="w-2.5 h-2.5" /> SELECT
                    </span>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
export default SearchBar;
