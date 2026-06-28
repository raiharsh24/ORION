import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useSystemStore } from '../store/useSystemStore';
import { Input } from '../components/ui/Input';
import { Search, Bell, Command, Menu } from 'lucide-react';

export const TopBar: React.FC = () => {
  const { sidebarOpen, toggleSidebar, user } = useSystemStore();
  const location = useLocation();
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatPathname = (path: string) => {
    if (path === '/') return 'DASHBOARD';
    return path.replace('/', '').toUpperCase();
  };

  return (
    <header className="h-20 bg-matte-card/80 border-b border-matte-border backdrop-blur-md px-6 flex items-center justify-between z-20 w-full">
      {/* Left side: Menu toggle & Breadcrumbs */}
      <div className="flex items-center gap-4">
        {!sidebarOpen && (
          <button 
            onClick={toggleSidebar}
            className="p-2 rounded-lg border border-matte-border hover:border-cyan-border/30 text-zinc-400 hover:text-cyan-glow transition-colors focus:outline-none"
            aria-label="Expand Sidebar"
          >
            <Menu className="w-4 h-4" />
          </button>
        )}
        
        {/* Dynamic Breadcrumbs */}
        <div className="flex items-center gap-2 font-mono text-xs tracking-wider">
          <span className="text-zinc-500">SYSTEM</span>
          <span className="text-zinc-700">/</span>
          <span className="text-cyan-glow font-semibold">
            {formatPathname(location.pathname)}
          </span>
        </div>
      </div>

      {/* Right side: Global Search + Time + User Info */}
      <div className="flex items-center gap-6">
        {/* Search Command Input */}
        <div className="hidden md:block w-72">
          <Input 
            icon={<Search className="w-4 h-4 text-zinc-500" />}
            suffixIcon={
              <div className="flex items-center gap-0.5 border border-matte-border px-1.5 py-0.5 rounded text-[9px] text-zinc-500 bg-black/40">
                <Command className="w-2.5 h-2.5" />
                <span>K</span>
              </div>
            }
            placeholder="Search system..."
            className="h-10"
          />
        </div>

        {/* System Time clock */}
        <div className="hidden sm:flex flex-col items-end font-mono text-xs text-zinc-400">
          <span>{time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</span>
          <span className="text-[9px] text-zinc-600 uppercase tracking-widest">SECURE STREAM</span>
        </div>

        {/* Notifications and profile */}
        <div className="flex items-center gap-4 border-l border-matte-border/50 pl-6">
          <button className="relative p-2 rounded-lg border border-matte-border/50 text-zinc-400 hover:text-cyan-glow hover:border-cyan-border/20 transition-all focus:outline-none">
            <span className="absolute top-1.5 right-1.5 flex h-1.5 w-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400"></span>
            </span>
            <Bell className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-3">
            <div className="flex flex-col text-right hidden lg:flex">
              <span className="text-xs font-bold text-zinc-200 leading-tight">{user.name}</span>
              <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-wider">{user.role}</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
