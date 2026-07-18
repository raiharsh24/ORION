import React, { useEffect, useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useSystemStore } from '../store/useSystemStore';

const PAGE_TITLES: Record<string, string> = {
  '/': 'Dashboard',
  '/assistant': 'Assistant',
  '/missions': 'Missions',
  '/cognitive': 'Cognitive OS',
  '/knowledge': 'Knowledge',
  '/projects': 'Projects',
  '/developer': 'Developer',
  '/plugins': 'Plugins',
  '/settings': 'Settings',
};

export const DashboardLayout: React.FC = () => {
  const [coords, setCoords] = useState({ x: 0, y: 0 });
  const checkBackendStatus = useSystemStore((state) => state.checkBackendStatus);
  const fetchSessions = useSystemStore((state) => state.fetchSessions);
  const location = useLocation();

  useEffect(() => {
    const title = PAGE_TITLES[location.pathname] || 'FRIDAY';
    document.title = `${title} — FRIDAY`;
  }, [location.pathname]);

  useEffect(() => {
    checkBackendStatus();
    fetchSessions();

    const interval = setInterval(() => {
      checkBackendStatus();
    }, 10000);

    return () => clearInterval(interval);
  }, [checkBackendStatus, fetchSessions]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setCoords({
        x: e.clientX,
        y: e.clientY,
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div 
      className="relative min-h-screen w-full overflow-hidden bg-matte-black text-zinc-100 flex"
      style={{
        // @ts-ignore
        '--x': `${coords.x}px`,
        // @ts-ignore
        '--y': `${coords.y}px`,
      }}
    >
      {/* Background Elements */}
      <div className="absolute inset-0 grid-backdrop pointer-events-none z-0" />
      <div className="absolute inset-0 radial-glow pointer-events-none z-0" />
      <div className="absolute inset-0 noise-overlay pointer-events-none z-0" />
      <div className="cyan-scanline z-0" />

      {/* Left Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-screen overflow-hidden z-10">
        {/* Top bar with Breadcrumbs & Profile */}
        <TopBar />

        {/* Dynamic Route Content */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto w-full h-full">
            <AnimatePresence mode="wait">
              <motion.div
                key={location.pathname}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
                className="h-full"
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
};
