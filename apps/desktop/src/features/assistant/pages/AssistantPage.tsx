import React, { useState } from 'react';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { useSystemStore } from '../../../store/useSystemStore';
import { 
  Bot, 
  User, 
  Send, 
  MessageSquare, 
  Plus, 
  Activity,
  AlertTriangle
} from 'lucide-react';

export const AssistantPage: React.FC = () => {
  const {
    sessions,
    currentSessionId,
    chatMessages,
    streamingMessage,
    apiConnected,
    lastTelemetry,
    lastIntent,
    lastExecutionTimeMs,
    lastToolUsed,
    logs,
    pendingConfirmation,
    setSession,
    sendMessageStream,
    confirmPendingAction,
    cancelPendingAction,
    createNewSession
  } = useSystemStore();

  const [inputVal, setInputVal] = useState('');
  const [showDiagnostics, setShowDiagnostics] = useState(true);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    const prompt = inputVal;
    setInputVal('');
    await sendMessageStream(prompt);
  };

  const formatTimestamp = (ts?: number) => {
    if (!ts) return '';
    return new Date(ts * 1000).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  };

  return (
    <div className="w-full grid grid-cols-1 lg:grid-cols-4 gap-6 h-[calc(100vh-12rem)] min-h-[500px]">
      
      {/* Session History Left Sidebar */}
      <div className="lg:col-span-1 flex flex-col justify-between space-y-4">
        <div className="flex flex-col h-full bg-matte-card/45 border border-matte-border rounded-2xl overflow-hidden p-4">
          <div className="flex items-center justify-between mb-4 pb-3 border-b border-matte-border/30">
            <span className="font-mono text-xs font-semibold tracking-wider text-zinc-400 uppercase">Conversations</span>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={createNewSession}
              className="p-1.5 h-8 w-8 rounded-lg"
              title="New Chat"
            >
              <Plus className="w-4 h-4 text-cyan-glow" />
            </Button>
          </div>
          
          <div className="flex-1 overflow-y-auto space-y-2 scrollbar-none pr-1">
            {sessions.length === 0 ? (
              <div className="text-center py-8 font-mono text-[10px] text-zinc-600">
                NO ACTIVE SESSIONS
              </div>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => setSession(s.session_id)}
                  className={`w-full text-left p-3 rounded-xl border font-mono text-[11px] transition-all flex flex-col gap-1
                    ${currentSessionId === s.session_id
                      ? 'bg-cyan-dim/40 border-cyan-border/50 text-cyan-glow shadow-[0_0_15px_rgba(0,242,254,0.03)]'
                      : 'bg-black/20 border-matte-border hover:border-cyan-border/20 text-zinc-400 hover:text-zinc-200'}`}
                >
                  <div className="font-semibold truncate uppercase tracking-wider">
                    {s.session_id.substring(0, 8)}...
                  </div>
                  <div className="text-[9px] text-zinc-500 truncate mt-0.5">
                    {s.summary || 'Active Session'}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Main Conversational Panel */}
      <div className="lg:col-span-3 flex flex-col justify-between space-y-4 h-full">
        
        {/* Top telemetry and diagnostics selector */}
        <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-matte-card/60 border border-matte-border rounded-2xl">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className={`relative flex h-2.5 w-2.5`}>
                {apiConnected ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                  </>
                ) : (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
                  </>
                )}
              </span>
              <span className="font-mono text-xs text-zinc-300 font-semibold">
                {apiConnected ? 'SYSTEM ACTIVE' : 'CONNECTION OFFLINE'}
              </span>
            </div>
            <span className="text-zinc-700">|</span>
            <span className="font-mono text-[10px] text-zinc-500">PROVIDER: GEMINI-1.5-FLASH</span>
          </div>

          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setShowDiagnostics(!showDiagnostics)}
            className="text-[10px] font-mono tracking-wider h-8"
          >
            <Activity className="w-3.5 h-3.5 mr-1 text-cyan-glow" />
            {showDiagnostics ? 'HIDE TELEMETRY' : 'SHOW TELEMETRY'}
          </Button>
        </div>

        {/* Diagnostic Telemetry Panel */}
        {showDiagnostics && (
          <div className="space-y-3 p-4 bg-black/45 border border-matte-border rounded-xl font-mono text-[10px] text-zinc-400 select-text">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex flex-col gap-0.5 border-r border-matte-border/50 pr-2">
                <span className="text-zinc-600 uppercase tracking-widest text-[9px]">Last Intent</span>
                <span className="text-cyan-glow font-bold truncate">{lastIntent || 'STDBY'}</span>
              </div>
              <div className="flex flex-col gap-0.5 border-r border-matte-border/50 pr-2">
                <span className="text-zinc-600 uppercase tracking-widest text-[9px]">API Latency</span>
                <span className="text-zinc-200 font-bold truncate">
                  {lastExecutionTimeMs ? `${lastExecutionTimeMs}ms` : '0ms'}
                </span>
              </div>
              <div className="flex flex-col gap-0.5 border-r border-matte-border/50 pr-2">
                <span className="text-zinc-600 uppercase tracking-widest text-[9px]">Prompt/Completion</span>
                <span className="text-zinc-200 font-bold">
                  {lastTelemetry?.prompt_tokens || 0} / {lastTelemetry?.completion_tokens || 0}
                </span>
              </div>
              <div className="flex flex-col gap-0.5">
                <span className="text-zinc-600 uppercase tracking-widest text-[9px]">Total Tokens</span>
                <span className="text-zinc-200 font-bold">{lastTelemetry?.total_tokens || 0}</span>
              </div>
            </div>
            {(lastToolUsed || logs.length > 0) && (
              <div className="pt-2 border-t border-matte-border/30 grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex flex-col gap-0.5">
                  <span className="text-zinc-600 uppercase tracking-widest text-[9px]">Last Executed Tool</span>
                  <span className="text-cyan-glow font-bold truncate">{lastToolUsed || 'NONE'}</span>
                </div>
                <div className="flex flex-col gap-0.5">
                  <span className="text-zinc-600 uppercase tracking-widest text-[9px]">Recent Tool Log</span>
                  <span className="text-zinc-300 truncate">
                    {logs.filter(l => l.message.includes('Tool') || l.message.includes('payload') || l.message.includes('Result')).slice(-1)[0]?.message || 'No tool telemetry logged.'}
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Message stream panel */}
        <Card variant="glow" className="flex-1 flex flex-col justify-between overflow-hidden relative">
          
          <div className="flex-1 p-6 space-y-6 overflow-y-auto scrollbar-thin select-text">
            {chatMessages.length === 0 && !streamingMessage ? (
              <div className="h-full flex flex-col justify-center items-center text-center opacity-60">
                <Bot className="w-10 h-10 text-cyan-glow/50 mb-3 animate-pulse" />
                <h3 className="text-sm font-semibold text-zinc-300">ORION Synaptic Interface</h3>
                <p className="text-xs text-zinc-500 font-mono mt-1 max-w-[280px]">
                  Start typing to execute backend instructions or query memories.
                </p>
              </div>
            ) : (
              <>
                {chatMessages.map((msg, index) => (
                  <div 
                    key={index}
                    className={`flex gap-4 max-w-2xl ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
                  >
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 border 
                      ${msg.role === 'user' 
                        ? 'bg-zinc-800 border-zinc-700 text-zinc-300' 
                        : 'bg-black border-cyan-border/40 text-cyan-glow'}`}
                    >
                      {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>
                    <div className="space-y-1.5 max-w-[85%]">
                      <div className={`rounded-2xl p-4 text-sm leading-relaxed border whitespace-pre-wrap
                        ${msg.role === 'user' 
                          ? 'bg-zinc-900 border-matte-border text-zinc-200' 
                          : 'bg-cyan-dim/20 border-cyan-border/10 text-cyan-glow/95 shadow-[0_0_15px_rgba(0,242,254,0.01)]'}`}
                      >
                        {msg.content}
                      </div>
                      <div className="text-[9px] font-mono text-zinc-600 px-1">
                        {formatTimestamp(msg.timestamp)}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Streaming Chunk Output */}
                {streamingMessage !== null && (
                  <div className="flex gap-4 max-w-2xl">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 border bg-black border-cyan-border/40 text-cyan-glow">
                      <Bot className="w-4 h-4" />
                    </div>
                    <div className="space-y-1.5 max-w-[85%]">
                      <div className="rounded-2xl p-4 text-sm leading-relaxed border bg-cyan-dim/20 border-cyan-border/10 text-cyan-glow/95 shadow-[0_0_15px_rgba(0,242,254,0.01)] whitespace-pre-wrap">
                        {streamingMessage || '...'}
                        <span className="inline-block w-1.5 h-4 bg-cyan-glow animate-pulse ml-0.5 align-middle" />
                      </div>
                      <div className="text-[9px] font-mono text-zinc-600 px-1">
                        Streaming...
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Interactive Confirmation Panel */}
          {pendingConfirmation && (
            <div className="p-4 border-t border-rose-500/20 bg-rose-950/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-in fade-in slide-in-from-bottom duration-300">
              <div className="space-y-1">
                <div className="text-xs font-mono font-bold text-rose-400 tracking-wider uppercase flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-rose-400 animate-pulse" />
                  Security Confirmation Needed
                </div>
                <div className="text-xs text-zinc-300 font-mono">
                  The tool <span className="text-rose-300 font-semibold">{pendingConfirmation.toolName}</span> is requesting permission to run.
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Button 
                  onClick={confirmPendingAction} 
                  className="bg-cyan-glow hover:bg-cyan-glow/85 text-black border-none font-bold text-xs px-4 py-2 h-9"
                >
                  CONFIRM EXECUTION
                </Button>
                <Button 
                  onClick={cancelPendingAction} 
                  variant="outline" 
                  className="border-rose-500/30 text-rose-400 hover:bg-rose-950/20 text-xs px-4 py-2 font-bold h-9"
                >
                  CANCEL
                </Button>
              </div>
            </div>
          )}

          {/* Form prompts inputs */}
          <form onSubmit={handleSubmit} className="p-4 border-t border-matte-border bg-black/30">
            <div className="flex items-center gap-3">
              <Input
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                placeholder={pendingConfirmation ? "Waiting for action confirmation..." : "Ask ORION ('run command echo hello', 'read file context.txt')..."}
                className="flex-1"
                icon={<MessageSquare className="w-4 h-4 text-zinc-600" />}
                disabled={streamingMessage !== null || pendingConfirmation !== null}
              />
              <Button 
                type="submit" 
                className="h-[42px] px-6" 
                disabled={streamingMessage !== null || pendingConfirmation !== null || !inputVal.trim()}
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </form>

        </Card>

      </div>

    </div>
  );
};
