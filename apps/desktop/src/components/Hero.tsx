import React, { useState, useEffect, useRef } from 'react';
import { Terminal, Cpu, Shield, Sparkles, ChevronRight, Activity, Globe, Clock } from 'lucide-react';
import { useSystemStore } from '../store/useSystemStore';

export const Hero: React.FC = () => {
  const [command, setCommand] = useState('');
  const [time, setTime] = useState(new Date());
  const [systemLogs, setSystemLogs] = useState<string[]>([
    'Core kernel loaded successfully.',
    'Neural interfaces initialized.',
    'Awaiting connection handshake...',
  ]);
  const [isStreaming, setIsStreaming] = useState(false);

  const sendMessageStream = useSystemStore((state) => state.sendMessageStream);
  const streamingMessage = useSystemStore((state) => state.streamingMessage);
  const checkBackendStatus = useSystemStore((state) => state.checkBackendStatus);

  const consoleEndRef = useRef<HTMLDivElement>(null);

  // Update clock every second
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Scroll to bottom of terminal console
  useEffect(() => {
    consoleEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [systemLogs, streamingMessage, isStreaming]);

  const handleCommandSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!command.trim()) return;

    const query = command;
    setCommand('');

    const newLog = `usr@orion:~$ ${query}`;
    const cmd = query.toLowerCase().trim();

    if (cmd === 'help') {
      setSystemLogs((prev) => [...prev, newLog, 'Available modules: system, diagnostics, neural, clear']);
    } else if (cmd === 'system') {
      setSystemLogs((prev) => [...prev, newLog, 'ORION OS v0.1.0 // Kernel: Darwin/Linux // Arch: ARM64/x64']);
    } else if (cmd === 'diagnostics') {
      setSystemLogs((prev) => [...prev, newLog, 'All subsystems nominal. Latency: 4ms. Integrity: 100%']);
    } else if (cmd === 'neural') {
      setSystemLogs((prev) => [...prev, newLog, 'Cognitive link status: Standby. Ready for input.']);
    } else if (cmd === 'clear') {
      setSystemLogs([]);
    } else {
      // It's an AI prompt!
      setSystemLogs((prev) => [...prev, newLog]);
      setIsStreaming(true);

      try {
        await checkBackendStatus();
        await sendMessageStream(query);

        // Fetch final result from history to freeze it in logs
        const chatMessages = useSystemStore.getState().chatMessages;
        const lastMsg = chatMessages[chatMessages.length - 1];
        const response = lastMsg ? lastMsg.content : 'No response received from system kernel.';
        
        setSystemLogs((prev) => [...prev, response]);
      } catch (err: any) {
        setSystemLogs((prev) => [...prev, `Error: ${err.message || 'Cognitive link error occurred.'}`]);
      } finally {
        setIsStreaming(false);
      }
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  };

  return (
    <div className="w-full flex flex-col items-center select-none">
      
      {/* Visual top beacon */}
      <div className="relative mb-8 flex justify-center items-center">
        <div className="absolute w-24 h-24 rounded-full bg-cyan-glow/5 blur-xl animate-pulse-glow" />
        <div className="w-12 h-12 rounded-xl bg-matte-card border border-cyan-border/50 flex items-center justify-center shadow-lg shadow-cyan-glow/5">
          <Sparkles className="w-5 h-5 text-cyan-glow" />
        </div>
      </div>

      {/* Main OS Brand */}
      <h1 className="text-7xl md:text-8xl lg:text-9xl font-extrabold tracking-[0.2em] text-center bg-gradient-to-b from-white via-zinc-200 to-zinc-600 bg-clip-text text-transparent drop-shadow-[0_0_30px_rgba(0,242,254,0.15)] select-text">
        ORION
      </h1>
      
      <p className="mt-4 font-mono text-sm md:text-base tracking-[0.4em] text-cyan-glow uppercase font-medium">
        AI Operating System
      </p>

      {/* Greeting and Status Panel */}
      <div className="mt-16 w-full max-w-md bg-matte-card/80 border border-matte-border backdrop-blur-md rounded-2xl p-6 relative overflow-hidden transition-all duration-300 hover:border-cyan-border/30">
        
        {/* Decorative corner highlights */}
        <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-cyan-glow/30" />
        <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-cyan-glow/30" />
        <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-cyan-glow/30" />
        <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-cyan-glow/30" />

        {/* Greeting Section */}
        <div className="flex justify-between items-start mb-6">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-zinc-100">
              Good Afternoon, Harsh.
            </h2>
            <div className="flex items-center gap-2 mt-1.5">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-400"></span>
              </span>
              <span className="text-xs font-mono text-zinc-400">
                Ready when you are.
              </span>
            </div>
          </div>
          <div className="flex flex-col items-end font-mono text-xs text-zinc-500">
            <span className="flex items-center gap-1.5 text-zinc-400">
              <Clock className="w-3.5 h-3.5 text-cyan-glow/80" />
              {formatTime(time)}
            </span>
            <span className="text-[10px] mt-0.5 text-zinc-600">GMT+05:30</span>
          </div>
        </div>

        {/* Console / Terminal Log area */}
        <div className="bg-black/60 border border-matte-border/80 rounded-xl p-4 font-mono text-xs text-zinc-400 min-h-[100px] max-h-[140px] overflow-y-auto mb-4 scrollbar-thin">
          {systemLogs.map((log, index) => (
            <div key={index} className="mb-1 leading-relaxed">
              {log.startsWith('usr@orion') ? (
                <span className="text-zinc-500">{log}</span>
              ) : log.startsWith('Error') ? (
                <span className="text-rose-400">{log}</span>
              ) : (
                <span className="text-cyan-glow/90">{log}</span>
              )}
            </div>
          ))}
          {/* Render active streaming message if any */}
          {isStreaming && streamingMessage && (
            <div className="mb-1 leading-relaxed text-cyan-glow/90">
              {streamingMessage}
              <span className="inline-block w-1.5 h-3.5 ml-1 bg-cyan-glow/80 animate-pulse" />
            </div>
          )}
          {/* If streaming but no chunks received yet, show thinking cursor */}
          {isStreaming && !streamingMessage && (
            <div className="mb-1 leading-relaxed text-zinc-600 animate-pulse">
              <span>Thinking...</span>
              <span className="inline-block w-1.5 h-3.5 ml-1 bg-zinc-600" />
            </div>
          )}
          <div ref={consoleEndRef} />
        </div>

        {/* Command Bar Interface */}
        <form onSubmit={handleCommandSubmit} className="relative">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
            <Terminal className="w-4 h-4 text-cyan-glow/60" />
          </div>
          <input
            type="text"
            className="w-full bg-black/40 border border-matte-border hover:border-cyan-border/40 focus:border-cyan-glow/80 focus:ring-1 focus:ring-cyan-glow/40 rounded-xl py-2.5 pl-10 pr-10 text-xs font-mono text-zinc-200 placeholder-zinc-600 focus:outline-none transition-all"
            placeholder="Type command ('help', 'system')..."
            value={command}
            onChange={(e) => setCommand(e.target.value)}
          />
          <button
            type="submit"
            className="absolute inset-y-0 right-0 pr-3 flex items-center text-cyan-glow/60 hover:text-cyan-glow transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </form>
      </div>

      {/* Grid of OS Services */}
      <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-2xl px-4">
        {[
          { label: 'Diagnostics', desc: 'System integrity', icon: Activity, val: '100% OK' },
          { label: 'Neural link', desc: 'Synaptic model', icon: Cpu, val: 'STDBY' },
          { label: 'Shield core', desc: 'Sandbox sandbox', icon: Shield, val: 'SECURE' },
          { label: 'Network', desc: 'Agent sync protocol', icon: Globe, val: 'ONLINE' },
        ].map((item, idx) => (
          <div 
            key={idx}
            className="bg-matte-card/40 border border-matte-border hover:border-cyan-border/20 rounded-xl p-4 flex flex-col justify-between items-start transition-all hover:bg-matte-card/60"
          >
            <div className="flex items-center justify-between w-full mb-3">
              <div className="p-1.5 rounded-lg bg-zinc-950 border border-matte-border text-zinc-400">
                <item.icon className="w-4 h-4 text-cyan-glow/85" />
              </div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider">{item.val}</span>
            </div>
            <div>
              <h3 className="text-xs font-semibold text-zinc-200">{item.label}</h3>
              <p className="text-[10px] text-zinc-500 mt-0.5">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
