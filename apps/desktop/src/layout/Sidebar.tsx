import React from 'react';
import { NavLink } from 'react-router-dom';
import { useSystemStore } from '../store/useSystemStore';
import { 
  LayoutDashboard, 
  MessageSquareCode, 
  Database, 
  FolderGit, 
  Terminal, 
  Blocks, 
  Settings, 
  ChevronLeft, 
  ChevronRight,
  Sparkles,
  ListTodo,
  Cpu
} from 'lucide-react';

export const Sidebar: React.FC = () => {
  const { sidebarOpen, toggleSidebar, systemStatus } = useSystemStore();

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Assistant', path: '/assistant', icon: MessageSquareCode },
    { name: 'Missions', path: '/missions', icon: ListTodo },
    { name: 'Cognitive OS', path: '/cognitive', icon: Cpu },
    { name: 'Knowledge', path: '/knowledge', icon: Database },
    { name: 'Projects', path: '/projects', icon: FolderGit },
    { name: 'Developer', path: '/developer', icon: Terminal },
    { name: 'Plugins', path: '/plugins', icon: Blocks },
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  return (
    <aside 
      className={`h-screen bg-matte-card/95 border-r border-matte-border flex flex-col justify-between transition-all duration-300 z-30 select-none
        ${sidebarOpen ? 'w-64' : 'w-20'}
      `}
    >
      {/* Brand area */}
      <div className="p-6 flex items-center justify-between border-b border-matte-border/30 h-20">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-8 h-8 rounded-lg bg-black border border-cyan-border/50 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-4 h-4 text-cyan-glow" />
          </div>
          {sidebarOpen && (
            <span className="font-extrabold tracking-[0.15em] text-zinc-100 text-lg uppercase font-sans">
              FRIDAY
            </span>
          )}
        </div>
        
        {/* Toggle Collapse Button */}
        {sidebarOpen && (
          <button 
            onClick={toggleSidebar}
            className="p-1 rounded-lg border border-matte-border hover:border-cyan-border/30 text-zinc-500 hover:text-cyan-glow transition-colors focus:outline-none"
            aria-label="Collapse Sidebar"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        )}
      </div>

      {/* Navigation list */}
      <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto scrollbar-none">
        {!sidebarOpen && (
          <div className="flex justify-center mb-4">
            <button 
              onClick={toggleSidebar}
              className="p-2 rounded-lg border border-matte-border hover:border-cyan-border/30 text-zinc-500 hover:text-cyan-glow transition-colors focus:outline-none"
              aria-label="Expand Sidebar"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {navItems.map((item) => (
          <NavLink
            key={item.name}
            to={item.path}
            className={({ isActive }) => `
              flex items-center gap-3.5 px-3.5 py-3 rounded-xl font-mono text-xs tracking-wider transition-all duration-200 group relative
              ${isActive 
                ? 'bg-cyan-dim text-cyan-glow border-l-2 border-cyan-glow shadow-[0_0_15px_rgba(0,242,254,0.05)]' 
                : 'text-zinc-500 hover:text-zinc-200 hover:bg-white/5 border-l-2 border-transparent'}
              ${!sidebarOpen ? 'justify-center px-0' : ''}
            `}
            title={!sidebarOpen ? item.name : undefined}
          >
            <item.icon className="w-5 h-5 flex-shrink-0" />
            {sidebarOpen && (
              <span className="font-medium tracking-wide">
                {item.name}
              </span>
            )}
            
            {/* Tooltip for collapsed state */}
            {!sidebarOpen && (
              <div className="absolute left-16 bg-black border border-matte-border text-zinc-200 text-[10px] tracking-widest px-2.5 py-1.5 rounded-lg opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap uppercase">
                {item.name}
              </div>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom Profile / Info */}
      <div className="p-4 border-t border-matte-border/30 flex items-center justify-between h-20 bg-black/20">
        <div className="flex items-center gap-3 overflow-hidden">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-glow/20 to-cyan-glow/5 border border-cyan-border/25 flex items-center justify-center text-xs font-bold text-cyan-glow font-mono flex-shrink-0">
            H
          </div>
          {sidebarOpen && (
            <div className="flex flex-col overflow-hidden">
              <span className="text-xs font-bold text-zinc-200 truncate">Harsh</span>
              <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-widest truncate">OS Admin</span>
            </div>
          )}
        </div>
        {sidebarOpen && (
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
            <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">{systemStatus}</span>
          </div>
        )}
      </div>
    </aside>
  );
};
