import React, { useState, useEffect, useRef } from 'react';
import { Card } from '../../../components/ui/Card';
import { Button } from '../../../components/ui/Button';
import { Input } from '../../../components/ui/Input';
import { useSystemStore } from '../../../store/useSystemStore';
import { missionApi } from '../../../services/api/missionApi';
import { WS_BASE_URL } from '../../../config/api';
import { useVoiceInput } from '../hooks/useVoiceInput';
import type { VoiceState } from '../hooks/useVoiceInput';
import type { Mission } from '../../../pages/MissionCenter/types';
import {
  useKernelStore,
  useTelemetryStore,
  useHealthStore,
  useWorkflowStore
} from '../../../pages/MissionCenter/store';
import { useRealtime } from '../../../services/realtime/hooks/useRealtime';
import { useMissionEvents } from '../../../services/realtime/hooks/useMissionEvents';
import { useTelemetry } from '../../../services/realtime/hooks/useTelemetry';
import { useKernelEvents } from '../../../services/realtime/hooks/useKernelEvents';
import {
  Bot,
  User,
  Send,
  MessageSquare,
  Plus,
  Activity,
  AlertTriangle,
  Cpu,
  Database,
  ListTodo,
  Mic,
  MicOff,
  Play,
  Pause,
  Square,
  Search,
  Sparkles,
  Terminal,
  Workflow,
  Monitor,
  Camera,
  ClipboardCopy
} from 'lucide-react';

const Soundwave: React.FC<{ state: VoiceState; onBypass: () => void }> = ({ state, onBypass }) => {
  if (state === 'idle') return null;

  return (
    <div className="flex flex-col items-center justify-center p-6 bg-cyan-dim/15 border border-cyan-border/30 rounded-2xl animate-in fade-in duration-300 relative overflow-hidden backdrop-blur-sm shadow-[inset_0_0_20px_rgba(0,242,254,0.05)]">
      <style>{`
        @keyframes soundwave {
          0% { height: 15%; }
          100% { height: 100%; }
        }
      `}</style>
      
      <div className="flex items-center gap-1.5 h-14 mb-4">
        {[...Array(14)].map((_, i) => {
          const delay = `${i * 0.08}s`;
          const speed = state === 'listening' ? '0.5s' : state === 'speaking' ? '1.1s' : '1.7s';
          
          if (state === 'processing') {
            return (
              <span
                key={i}
                className="w-1.5 h-4 rounded-full bg-cyan-glow/40 animate-pulse"
                style={{ animationDelay: delay }}
              />
            );
          }

          return (
            <span
              key={i}
              className="w-1.5 rounded-full bg-cyan-glow shadow-[0_0_12px_rgba(0,242,254,0.4)]"
              style={{
                height: '100%',
                maxHeight: '44px',
                animation: `soundwave ${speed} ease-in-out infinite alternate`,
                animationDelay: delay,
              }}
            />
          );
        })}
      </div>
      
      <div className="font-mono text-xs uppercase tracking-widest text-cyan-glow flex items-center gap-2">
        {state === 'waking' && (
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 bg-yellow-400 rounded-full animate-ping" />
            Say "FRIDAY" or bypass wake word
          </span>
        )}
        {state === 'listening' && (
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
            Listening... Speak now
          </span>
        )}
        {state === 'processing' && (
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full border-2 border-cyan-glow border-t-transparent animate-spin" />
            Processing voice queries...
          </span>
        )}
        {state === 'speaking' && (
          <span className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full border-2 border-cyan-glow border-t-transparent animate-spin" />
            Friday speech streaming...
          </span>
        )}
      </div>
      
      {state === 'waking' && (
        <button
          type="button"
          onClick={onBypass}
          className="mt-3.5 text-[9px] font-mono tracking-widest px-3 py-1.5 bg-cyan-glow/10 border border-cyan-glow/30 text-cyan-glow rounded-xl hover:bg-cyan-glow hover:text-black transition-all cursor-pointer select-none uppercase font-bold"
        >
          Bypass Wake Word
        </button>
      )}
    </div>
  );
};

const OrchestrationFlowchart: React.FC<{
  lastIntent: string | null;
  lastToolUsed: string | null;
  pendingConfirmation: any;
  streamingMessage: string | null;
  lastExecutionTimeMs: number | null;
}> = ({
  lastIntent,
  lastToolUsed,
  pendingConfirmation,
  streamingMessage,
  lastExecutionTimeMs
}) => {
  const steps: { label: string; desc: string; status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'WARNING' }[] = [
    {
      label: 'Understand Intent',
      desc: lastIntent ? `Classified intent: ${lastIntent}` : 'Waiting for command intent parse...',
      status: lastIntent ? 'COMPLETED' : streamingMessage ? 'RUNNING' : 'PENDING'
    },
    {
      label: 'Verify Permissions',
      desc: pendingConfirmation
        ? `Awaiting sandbox authorization: ${pendingConfirmation.toolName}`
        : (lastToolUsed || lastExecutionTimeMs)
          ? 'Sandbox access granted'
          : 'Security loops nominal',
      status: pendingConfirmation ? 'WARNING' : (lastToolUsed || lastExecutionTimeMs) ? 'COMPLETED' : 'PENDING'
    },
    {
      label: 'Execute Tool Call',
      desc: lastToolUsed
        ? `Driver call: ${lastToolUsed.toUpperCase()}`
        : streamingMessage
          ? 'Streaming LLM completion responses'
          : 'Standby for driver execution',
      status: lastToolUsed ? 'COMPLETED' : streamingMessage ? 'RUNNING' : 'PENDING'
    },
    {
      label: 'Record Memory Index',
      desc: lastIntent === 'KNOWLEDGE_SEARCH'
        ? 'Querying semantic collections index'
        : lastExecutionTimeMs
          ? 'Cognitive buffer committed'
          : 'Embedding synchronization standby',
      status: lastExecutionTimeMs ? 'COMPLETED' : (streamingMessage || lastIntent === 'KNOWLEDGE_SEARCH') ? 'RUNNING' : 'PENDING'
    },
    {
      label: 'Notify Workspace UI',
      desc: lastExecutionTimeMs
        ? `Telemetry synced in ${lastExecutionTimeMs}ms`
        : 'Awaiting event bus completion broadcast',
      status: lastExecutionTimeMs ? 'COMPLETED' : streamingMessage ? 'RUNNING' : 'PENDING'
    }
  ];

  return (
    <div className="border border-cyan-border/20 bg-cyan-dim/5 rounded-xl p-4 font-mono text-[9px] space-y-3 mt-4">
      <div className="font-bold text-cyan-glow uppercase tracking-widest flex items-center gap-1.5 border-b border-matte-border/20 pb-2 mb-2">
        <Workflow className="w-3.5 h-3.5 text-cyan-glow" />
        <span>FRIDAY COGNITIVE ORCHESTRATION PIPELINE</span>
      </div>
      <div className="space-y-3 pl-2.5 border-l-2 border-matte-border/50">
        {steps.map((step, idx) => (
          <div key={idx} className="relative flex items-start gap-3">
            <span className={`w-2.5 h-2.5 rounded-full mt-1 flex-shrink-0 border transition-all duration-300
              ${step.status === 'COMPLETED' ? 'bg-emerald-400 border-emerald-500 shadow-[0_0_8px_rgba(52,211,153,0.4)]' :
                step.status === 'RUNNING' ? 'bg-cyan-glow border-cyan-400 shadow-[0_0_8px_rgba(0,242,254,0.4)] animate-pulse' :
                step.status === 'WARNING' ? 'bg-amber-400 border-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.4)] animate-bounce' :
                'bg-zinc-800 border-zinc-700'}`}
            />
            <div className="flex-1 min-w-0">
              <div className="flex justify-between font-bold text-zinc-300 uppercase tracking-wide">
                <span>{step.label}</span>
                <span className={`text-[8px]
                  ${step.status === 'COMPLETED' ? 'text-emerald-400' :
                    step.status === 'RUNNING' ? 'text-cyan-glow' :
                    step.status === 'WARNING' ? 'text-amber-400' :
                    'text-zinc-650'}`}
                >
                  {step.status}
                </span>
              </div>
              <p className="text-zinc-500 text-[8.5px] mt-0.5 uppercase leading-normal">{step.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const AssistantPage: React.FC = () => {
  const {
    currentSessionId,
    chatMessages,
    streamingMessage,
    apiConnected,
    lastIntent,
    lastExecutionTimeMs,
    lastToolUsed,
    logs,
    pendingConfirmation,
    setSession,
    sendMessageStream,
    confirmPendingAction,
    cancelPendingAction,
    cancelCurrentRequest,
    createNewSession,
    addLog,
    fetchSessions,
    sessions
  } = useSystemStore();

  const [inputVal, setInputVal] = useState('');
  const [activeTab, setActiveTab] = useState<'missions' | 'desktop' | 'memory' | 'system'>('missions');
  const [isDragging, setIsDragging] = useState(false);
  const [showReasoning, setShowReasoning] = useState(true);
  
  // Mission active list state
  const [missions, setMissions] = useState<Mission[]>([]);
  const [expandedMissionId, setExpandedMissionId] = useState<string | null>(null);

  // Vector store states
  const [memoryQuery, setMemoryQuery] = useState('');
  const { searchResults, performKnowledgeSearch } = useSystemStore();

  // 1. Mount client WebSocket EventBus hooks
  const realtime = useRealtime();
  useMissionEvents();
  useTelemetry();
  useKernelEvents();

  // Pull active store utilities
  const loadKernel = useKernelStore((s) => s.loadKernel);
  const kernelState = useKernelStore();

  const loadTelemetry = useTelemetryStore((s) => s.loadTelemetry);
  const telemetryState = useTelemetryStore();

  const loadHealth = useHealthStore((s) => s.loadHealth);
  const healthState = useHealthStore();

  const loadWorkflows = useWorkflowStore((s) => s.loadWorkflows);
  const workflowState = useWorkflowStore();

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const voice = useVoiceInput(`${WS_BASE_URL}/ws/voice`, {
    onWakeWordDetected: (sid) => {
      addLog(`[Voice HUD] Wake word recognized. Session initialized: ${sid.substring(0, 8)}`, 'info');
    },
    onSpeechEnded: (_sid, dur) => {
      addLog(`[Voice HUD] Speech concluded. Capturing payload (${dur.toFixed(1)}s)`, 'info');
    },
    onSpeechFinalized: async (sid, transcript, _response) => {
      addLog(`[Voice HUD] Transcript finalized: "${transcript}"`, 'success');
      await fetchSessions();
      await setSession(sid);
    },
    onError: (msg) => {
      addLog(`[Voice HUD] Service error: ${msg}`, 'error');
    }
  });

  // Polling fallback trigger only if WebSocket is disconnected or polling
  const fetchMissionsAndWorkflows = async () => {
    try {
      const list = await missionApi.getMissions();
      setMissions(list);
    } catch {
      // Offline fallback
    }
    try {
      await Promise.all([
        loadWorkflows(),
        loadKernel(),
        loadTelemetry(),
        loadHealth()
      ]);
    } catch {
      // Offline fallback
    }
  };

  useEffect(() => {
    // Immediate sync
    fetchMissionsAndWorkflows();

    // Check transport. If WebSocket is connected, we don't start the poll interval!
    let interval: ReturnType<typeof setInterval> | null = null;
    if (realtime.transportType === 'POLLING' || realtime.connectionState !== 'CONNECTED') {
      interval = setInterval(fetchMissionsAndWorkflows, 2000);
      addLog('[System EventBus] WebSocket transport polling/offline. Active HTTP check initialized.', 'warn');
    } else {
      addLog('[System EventBus] Connected via WebSocket EventBus. Live subscriptions active.', 'success');
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [realtime.transportType, realtime.connectionState]);

  // Keyboard Shortcuts Handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape: close recordings or interrupts stream
      if (e.key === 'Escape') {
        if (voice.isRecording) {
          voice.stopRecording();
          addLog('[Hotkey] Microphone disabled.', 'warn');
        } else if (streamingMessage !== null) {
          cancelCurrentRequest();
          addLog('[Hotkey] Content stream cancelled.', 'warn');
        }
      }
      // Alt + V: Toggles recording
      if (e.altKey && e.key.toLowerCase() === 'v') {
        e.preventDefault();
        if (voice.isRecording) {
          voice.stopRecording();
        } else {
          voice.startRecording().catch(() => {});
        }
      }
      // Cmd/Ctrl + K: Focus semantic memory search input
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setActiveTab('memory');
        const el = document.getElementById('memory-search-input');
        el?.focus();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [voice.isRecording, streamingMessage, cancelCurrentRequest, addLog]);

  // Drag and Drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      addLog(`File attachment captured: ${file.name} (${file.size} bytes)`, 'success');
      setInputVal((prev) => {
        const prefix = prev.trim() ? `${prev} ` : '';
        return `${prefix}[attached source file: ${file.name}]`;
      });
    }
  };

  // Auto-scroll messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [chatMessages, streamingMessage, voice.voiceState]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    const prompt = inputVal;
    setInputVal('');
    await sendMessageStream(prompt);
  };

  const handleQuickAction = async (prompt: string) => {
    setInputVal('');
    await sendMessageStream(prompt);
  };

  const handleStartMission = async (id: string) => {
    try {
      addLog(`Starting background execution node for mission ${id.substring(0, 8)}`, 'info');
      await missionApi.startMission(id);
      fetchMissionsAndWorkflows();
    } catch (err: any) {
      addLog(`Mission start failed: ${err.message}`, 'error');
    }
  };

  const handlePauseMission = async (id: string) => {
    try {
      addLog(`Requesting suspension block on mission ${id.substring(0, 8)}`, 'warn');
      await missionApi.pauseMission(id);
      fetchMissionsAndWorkflows();
    } catch (err: any) {
      addLog(`Mission pause failed: ${err.message}`, 'error');
    }
  };

  const handleCancelMission = async (id: string) => {
    try {
      addLog(`Terminating active processes for mission ${id.substring(0, 8)}`, 'error');
      await missionApi.cancelMission(id);
      fetchMissionsAndWorkflows();
    } catch (err: any) {
      addLog(`Mission cancel failed: ${err.message}`, 'error');
    }
  };

  const handleMemorySearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memoryQuery.trim()) return;
    await performKnowledgeSearch(memoryQuery);
  };

  const formatTimestamp = (ts?: number) => {
    if (!ts) return '';
    return new Date(ts * 1000).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    });
  };

  // Resolve suggested chips
  const getSuggestions = () => {
    const list: string[] = [];
    if (lastIntent === 'KNOWLEDGE_SEARCH') {
      list.push('Scan document embeddings', 'Explain search weights');
    } else if (lastIntent === 'SYSTEM_COMMAND') {
      list.push('Inspect telemetry timeline', 'Verify loaded plugins');
    } else {
      list.push('Compile active project', 'Review recent logs');
    }
    list.push('Reset local workspace');
    return list.slice(0, 3);
  };

  const handleSuggestedAction = async (action: string) => {
    if (action === 'Reset local workspace') {
      useSystemStore.getState().clearLogs();
      addLog('Workspace logging console reset.', 'warn');
    } else {
      await sendMessageStream(action);
    }
  };

  const quickActions = [
    { title: 'Project Info', prompt: 'List active projects and describe structure', icon: Terminal },
    { title: 'System Diagnostics', prompt: 'Verify kernel environment modules status', icon: Activity },
    { title: 'Semantic Search', prompt: 'Search codebase vector index for main endpoints', icon: Search },
    { title: 'Security Audits', prompt: 'Audit loaded plugin execution permissions', icon: AlertTriangle }
  ];

  const currentWorkflow = workflowState.workflows.find(w => w.id === workflowState.activeWorkflowId) || null;
  const workflowNodes = currentWorkflow?.nodes ? Object.values(currentWorkflow.nodes) : [];

  return (
    <div className="flex flex-col lg:flex-row gap-6 h-[calc(100vh-7.5rem)] overflow-hidden text-zinc-200 font-sans select-none">
      
      {/* 1. Left Panel: Sessions & Context Library */}
      <div className="w-full lg:w-72 flex flex-col gap-4 h-full overflow-hidden flex-shrink-0">
        
        {/* Sessions Card */}
        <Card variant="glow" className="flex-1 flex flex-col min-h-0 bg-matte-card/65 border-matte-border/50">
          <div className="p-4 flex items-center justify-between border-b border-matte-border/30 h-14 flex-shrink-0 bg-black/25">
            <span className="font-mono text-[10px] font-bold tracking-widest text-zinc-400 uppercase">ACTIVE CONVERSATIONS</span>
            <Button
              variant="outline"
              size="sm"
              onClick={createNewSession}
              className="p-1 h-7 w-7 rounded-lg border-matte-border hover:border-cyan-border/40"
              title="New Session"
            >
              <Plus className="w-3.5 h-3.5 text-cyan-glow" />
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-2 scrollbar-none">
            {sessions.length === 0 ? (
              <div className="text-center py-10 font-mono text-[9px] text-zinc-600 uppercase tracking-widest">
                NO ACTIVE WORKSPACES
              </div>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.session_id}
                  onClick={() => setSession(s.session_id)}
                  className={`w-full text-left p-3 rounded-xl border font-mono text-[10px] transition-all flex flex-col gap-1 cursor-pointer
                    ${currentSessionId === s.session_id
                      ? 'bg-cyan-dim/20 border-cyan-border/40 text-cyan-glow shadow-[0_0_12px_rgba(0,242,254,0.02)]'
                      : 'bg-black/10 border-matte-border/40 hover:border-cyan-border/15 text-zinc-400 hover:text-zinc-200'}`}
                >
                  <div className="font-bold truncate uppercase tracking-widest flex items-center gap-1.5">
                    <span className={`w-1 h-1 rounded-full ${currentSessionId === s.session_id ? 'bg-cyan-glow animate-pulse' : 'bg-zinc-600'}`} />
                    {s.session_id.substring(0, 8)}
                  </div>
                  <div className="text-[9px] text-zinc-500 truncate mt-0.5 max-w-[220px]">
                    {s.summary || 'Active Session'}
                  </div>
                </button>
              ))
            )}
          </div>
        </Card>

        {/* Context library actions */}
        <Card variant="flat" className="h-52 flex flex-col min-h-0 bg-black/20 border-matte-border/40 flex-shrink-0">
          <div className="p-3.5 border-b border-matte-border/30 font-mono text-[9px] tracking-widest text-zinc-500 uppercase flex-shrink-0">
            PROACTIVE ACTIONS
          </div>
          <div className="flex-1 overflow-y-auto p-3 grid grid-cols-2 gap-2 scrollbar-none">
            {quickActions.map((action, idx) => (
              <button
                key={idx}
                onClick={() => handleQuickAction(action.prompt)}
                className="flex flex-col items-start gap-1 p-2 bg-matte-card/45 border border-matte-border/40 hover:border-cyan-border/20 hover:bg-cyan-dim/5 rounded-xl text-left transition-all cursor-pointer font-mono text-[9px]"
              >
                <action.icon className="w-3.5 h-3.5 text-cyan-glow/85" />
                <span className="text-zinc-300 font-semibold truncate w-full">{action.title}</span>
              </button>
            ))}
          </div>
        </Card>
      </div>

      {/* 2. Center Panel: Conversational OS Core */}
      <div className="flex-1 flex flex-col gap-4 h-full overflow-hidden min-w-0">
        
        {/* Workspace Telemetry Header */}
        <div className="h-14 bg-matte-card/65 border border-matte-border/40 rounded-2xl flex items-center justify-between px-4 flex-shrink-0 backdrop-blur-md">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <span className="relative flex h-2 w-2">
                {apiConnected ? (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-glow"></span>
                  </>
                ) : (
                  <>
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
                  </>
                )}
              </span>
              <span className="font-mono text-[10px] tracking-widest font-bold text-zinc-300 uppercase">
                {apiConnected ? `AI RUNSTATE: ${kernelState.kernelState}` : 'SYSTEM LINK OFFLINE'}
              </span>
            </div>
            <span className="text-zinc-800">|</span>
            <div className="flex items-center gap-1 font-mono text-[9px] text-zinc-500">
              <span className="uppercase font-semibold">INTENT:</span>
              <span className="text-cyan-glow/80 font-bold">{lastIntent || 'STANDBY'}</span>
            </div>
          </div>

          <div className="flex items-center gap-4 font-mono text-[9px] text-zinc-500">
            {lastExecutionTimeMs && lastExecutionTimeMs > 0 ? (
              <span className="hidden sm:inline">LATENCY: <strong className="text-zinc-300 font-normal">{lastExecutionTimeMs}ms</strong></span>
            ) : null}
            {lastToolUsed ? (
              <span className="hidden md:inline border border-cyan-border/20 px-2 py-0.5 rounded bg-cyan-dim/5 text-cyan-glow font-bold">
                TOOL: {lastToolUsed.toUpperCase()}
              </span>
            ) : null}
          </div>
        </div>

        {/* Message feed panel with drag & drop zone */}
        <Card
          variant="glow"
          className="flex-1 flex flex-col justify-between overflow-hidden relative bg-matte-card/85 border-cyan-border/15"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          {/* Glassmorphic Drag Overlay */}
          {isDragging && (
            <div className="absolute inset-0 bg-black/60 border-2 border-dashed border-cyan-glow rounded-2xl flex flex-col items-center justify-center z-40 backdrop-blur-md animate-in fade-in duration-200">
              <Sparkles className="w-10 h-10 text-cyan-glow animate-bounce mb-3" />
              <p className="font-mono text-xs uppercase tracking-widest text-cyan-glow font-bold">
                Drop File to Seed FRIDAY Context
              </p>
            </div>
          )}
          
          <div className="flex-1 p-5 space-y-5 overflow-y-auto scrollbar-thin select-text">
            {chatMessages.length === 0 && !streamingMessage && voice.voiceState === 'idle' ? (
              <div className="h-full flex flex-col justify-center items-center text-center opacity-65">
                <div className="w-12 h-12 rounded-2xl bg-black border border-cyan-border/40 flex items-center justify-center mb-3.5 shadow-[0_0_15px_rgba(0,242,254,0.05)]">
                  <Sparkles className="w-5 h-5 text-cyan-glow animate-pulse" />
                </div>
                <h3 className="text-sm font-semibold tracking-wide text-zinc-200">FRIDAY COGNITIVE WORKSPACE</h3>
                <p className="text-[10px] text-zinc-500 font-mono mt-1.5 max-w-sm uppercase tracking-wider leading-relaxed">
                  Workspace interface loaded. Provide console commands, invoke backend tools, or select a proactive action.
                </p>
              </div>
            ) : (
              <>
                {chatMessages.map((msg, index) => (
                  <div
                    key={index}
                    className={`flex gap-3.5 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}
                  >
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 border font-mono text-[10px]
                      ${msg.role === 'user'
                        ? 'bg-zinc-900 border-matte-border text-zinc-400 shadow-md'
                        : 'bg-black border-cyan-border/30 text-cyan-glow shadow-[0_0_8px_rgba(0,242,254,0.05)]'}`}
                    >
                      {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                    </div>
                    <div className="space-y-1 w-full">
                      <div className={`rounded-2xl p-4 text-xs leading-relaxed border whitespace-pre-wrap font-mono select-text
                        ${msg.role === 'user'
                          ? 'bg-black/30 border-matte-border/50 text-zinc-200'
                          : 'bg-cyan-dim/10 border-cyan-border/10 text-zinc-300 shadow-[inset_0_0_15px_rgba(0,242,254,0.02)]'}`}
                      >
                        {msg.content}
                      </div>
                      <div className="text-[8px] font-mono text-zinc-600 px-1.5 flex justify-between items-center">
                        <span>{msg.role === 'user' ? 'CLIENT USER' : 'FRIDAY OS'}</span>
                        <span>{formatTimestamp(msg.timestamp)}</span>
                      </div>
                    </div>
                  </div>
                ))}

                {/* Streaming Chunk Output */}
                {streamingMessage !== null && (
                  <div className="flex gap-3.5 max-w-[85%]">
                    <div className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 border bg-black border-cyan-border/30 text-cyan-glow">
                      <Bot className="w-4 h-4" />
                    </div>
                    <div className="space-y-1 w-full">
                      <div className="rounded-2xl p-4 text-xs leading-relaxed border bg-cyan-dim/10 border-cyan-border/10 text-zinc-300 shadow-[inset_0_0_15px_rgba(0,242,254,0.02)] whitespace-pre-wrap font-mono">
                        {streamingMessage || 'Initializing Stream...'}
                        <span className="inline-block w-1.5 h-3.5 bg-cyan-glow animate-pulse ml-1.5 align-middle" />
                      </div>
                      <div className="text-[8px] font-mono text-zinc-600 px-1.5">
                        STREAMING CHUNKS...
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Collapsible Reasoning & Tool Execution block */}
            {(streamingMessage || lastToolUsed) && (
              <div className="border border-cyan-border/20 bg-cyan-dim/5 rounded-xl p-3.5 font-mono text-[9px] space-y-2 mt-2">
                <div
                  className="flex justify-between items-center cursor-pointer text-cyan-glow font-bold uppercase tracking-widest"
                  onClick={() => setShowReasoning(!showReasoning)}
                >
                  <span className="flex items-center gap-1.5">
                    <Terminal className="w-3.5 h-3.5 text-cyan-glow" />
                    {streamingMessage ? 'Friday Reasoning Engine' : `Executed Tool: ${lastToolUsed}`}
                  </span>
                  <span>{showReasoning ? 'HIDE DETAILS [-]' : 'SHOW DETAILS [+]'}</span>
                </div>
                
                {showReasoning && (
                  <div className="mt-2 space-y-2 text-zinc-400 pl-2.5 border-l border-cyan-border/30">
                    <div className="grid grid-cols-2 gap-3 pb-2 border-b border-matte-border/30">
                      <div>INTENT CLASSIFIER: <strong className="text-zinc-200">{lastIntent || 'CHAT'}</strong></div>
                      <div>ACTIVE DRIVER: <strong className="text-amber-400 font-bold">{lastToolUsed || 'STDBY'}</strong></div>
                      <div>CONTEXT OCCUPANCY: <span className="text-zinc-200">{((telemetryState.memory || 0) / 1024).toFixed(2)} MB / 256 MB</span></div>
                      <div>LATENCY PIN: <span className="text-zinc-200">{lastExecutionTimeMs || 0}ms</span></div>
                    </div>
                    {lastToolUsed && (
                      <div className="bg-black/40 p-2 rounded border border-matte-border/40 text-zinc-400 text-[8.5px] max-h-28 overflow-y-auto scrollbar-thin">
                        <span className="text-zinc-550 block font-bold border-b border-matte-border/20 pb-0.5 mb-1">TOOL INPUT ARGS:</span>
                        <pre className="text-zinc-350">{`{ "tool": "${lastToolUsed}", "session_id": "${currentSessionId?.substring(0, 8)}" }`}</pre>
                      </div>
                    )}
                    {streamingMessage && (
                      <div className="flex items-center gap-2 text-cyan-glow/80">
                        <span className="w-1.5 h-1.5 bg-cyan-400 rounded-full animate-ping" />
                        Synthesizing next completion segments...
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Visual Orchestration Flowchart Dashboard Panel */}
            {(streamingMessage || lastIntent) && (
              <OrchestrationFlowchart
                lastIntent={lastIntent}
                lastToolUsed={lastToolUsed}
                pendingConfirmation={pendingConfirmation}
                streamingMessage={streamingMessage}
                lastExecutionTimeMs={lastExecutionTimeMs}
              />
            )}

            {/* Proactive Suggested next actions chips */}
            {chatMessages.length > 0 && !streamingMessage && voice.voiceState === 'idle' && (
              <div className="flex flex-wrap gap-2.5 pt-2 pl-11">
                {getSuggestions().map((suggestion, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSuggestedAction(suggestion)}
                    className="px-2.5 py-1 bg-black/45 border border-matte-border hover:border-cyan-border/30 text-[8.5px] font-mono rounded-lg text-zinc-400 hover:text-cyan-glow transition-all cursor-pointer uppercase tracking-wider font-semibold"
                  >
                    💡 {suggestion}
                  </button>
                ))}
              </div>
            )}

            {/* Voice HUD panel nested inside conversation area */}
            <Soundwave state={voice.voiceState} onBypass={voice.triggerWakeWord} />
            <div ref={messagesEndRef} />
          </div>

          {/* Destructive actions safety loop confirmation banner */}
          {pendingConfirmation && (
            <div className="p-4 border-t border-rose-500/25 bg-rose-950/15 flex flex-col sm:flex-row sm:items-center justify-between gap-4 animate-in fade-in slide-in-from-bottom duration-300">
              <div className="space-y-1">
                <div className="text-[10px] font-mono font-bold text-rose-400 tracking-widest uppercase flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
                  SECURITY SANDBOX VERIFICATION
                </div>
                <div className="text-[10px] text-zinc-400 font-mono">
                  Confirm process call <strong className="text-rose-300 font-semibold">{pendingConfirmation.toolName}</strong> command payload.
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  onClick={confirmPendingAction}
                  className="bg-cyan-glow hover:bg-cyan-glow/85 text-black border-none font-bold text-[10px] tracking-wider px-3.5 py-1.5 h-8 uppercase"
                >
                  Approve Call
                </Button>
                <Button
                  onClick={cancelPendingAction}
                  variant="outline"
                  className="border-rose-500/25 text-rose-400 hover:bg-rose-500/10 text-[10px] tracking-wider px-3.5 py-1.5 h-8 font-bold uppercase"
                >
                  Reject
                </Button>
              </div>
            </div>
          )}

          {/* Form input controls */}
          <form onSubmit={handleSubmit} className="p-4 border-t border-matte-border/50 bg-black/35 flex-shrink-0">
            <div className="flex items-center gap-3">
              <div className="flex-1 relative flex items-center">
                <Input
                  id="assistant-prompt-input"
                  value={inputVal}
                  onChange={(e) => setInputVal(e.target.value)}
                  placeholder={
                    pendingConfirmation
                      ? "Verify security loop parameter..."
                      : voice.isRecording
                        ? `Voice capturing active: state is [${voice.voiceState.toUpperCase()}]`
                        : "Type command instruction or drop files here..."
                  }
                  className="w-full h-[42px] bg-black/60 font-mono text-xs placeholder-zinc-700 pr-12"
                  icon={<MessageSquare className="w-4.5 h-4.5 text-zinc-700" />}
                  disabled={streamingMessage !== null || pendingConfirmation !== null || voice.isRecording}
                />
                
                {/* Alt+V Keyboard helper label inside input container */}
                <div className="absolute right-3.5 text-[8px] font-mono text-zinc-600 uppercase border border-matte-border px-1.5 py-0.5 rounded pointer-events-none select-none bg-black/40">
                  {voice.isRecording ? 'ESC' : 'ALT+V'}
                </div>
              </div>

              {/* Voice micro interaction */}
              <Button
                type="button"
                onClick={voice.isRecording ? voice.stopRecording : voice.startRecording}
                className={`h-[42px] px-3.5 border transition-all ${
                  voice.isRecording
                    ? 'bg-rose-500/20 border-rose-500 text-rose-400 animate-pulse'
                    : 'bg-black border-matte-border hover:border-cyan-border/40 text-zinc-500 hover:text-cyan-glow'
                }`}
                title="Voice Engine Toggle (Alt+V)"
              >
                {voice.isRecording ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </Button>

              {streamingMessage !== null ? (
                <Button
                  type="button"
                  onClick={cancelCurrentRequest}
                  className="h-[42px] px-4 bg-rose-500/10 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 font-bold uppercase text-[10px] tracking-wider"
                  title="Stop Stream (ESC)"
                >
                  Stop
                </Button>
              ) : (
                <Button
                  type="submit"
                  className="h-[42px] px-5 bg-cyan-glow text-black font-semibold"
                  disabled={streamingMessage !== null || pendingConfirmation !== null || !inputVal.trim() || voice.isRecording}
                >
                  <Send className="w-3.5 h-3.5" />
                </Button>
              )}
            </div>
          </form>

        </Card>

      </div>

      {/* 3. Right Panel: Live OS Metrics / Missions & Memory Tabs */}
      <div className="w-full lg:w-80 flex flex-col gap-4 h-full overflow-hidden flex-shrink-0">
        <Card variant="glow" className="flex-1 flex flex-col min-h-0 bg-matte-card/65 border-matte-border/50">
          
          {/* Tab headers */}
          <div className="flex border-b border-matte-border/30 h-12 flex-shrink-0 bg-black/25">
            {[
              { id: 'missions', label: 'MISSIONS', icon: ListTodo },
              { id: 'desktop', label: 'DESKTOP', icon: Monitor },
              { id: 'memory', label: 'MEMORY', icon: Database },
              { id: 'system', label: 'SYSTEM', icon: Cpu }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex-1 flex items-center justify-center gap-1.5 font-mono text-[9px] tracking-widest font-bold border-b-2 transition-all cursor-pointer uppercase
                  ${activeTab === tab.id
                    ? 'border-cyan-glow text-cyan-glow bg-cyan-dim/5'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-white/5'}`}
              >
                <tab.icon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Tab panel bodies */}
          <div className="flex-1 overflow-y-auto p-4 scrollbar-none min-h-0 select-text">
            
            {/* Tab 1: Missions list & progress */}
            {activeTab === 'missions' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between font-mono text-[9px] text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-2">
                  <span>Active Mission Tasks</span>
                  <span className="text-cyan-glow font-bold">{missions.length} active</span>
                </div>

                {missions.length === 0 ? (
                  <div className="text-center py-10 font-mono text-[9px] text-zinc-600 uppercase tracking-widest leading-relaxed">
                    NO BACKGROUND MISSIONS SCHEDULED
                  </div>
                ) : (
                  <div className="space-y-3">
                    {missions.map((m) => (
                      <div
                        key={m.id}
                        className="bg-black/25 border border-matte-border/40 rounded-xl p-3.5 space-y-2.5 transition-all hover:border-matte-border/70"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="overflow-hidden">
                            <h4 className="font-mono text-[10px] font-bold text-zinc-200 uppercase tracking-wider truncate">
                              {m.name || 'Task Node'}
                            </h4>
                            <p className="text-[9px] font-mono text-zinc-500 truncate mt-0.5 uppercase">
                              {m.description || 'Background system service'}
                            </p>
                          </div>
                          
                          {/* Priority flag badge */}
                          <span className={`font-mono text-[8px] px-1.5 py-0.5 rounded border uppercase font-bold
                            ${m.priority === 'CRITICAL' ? 'bg-rose-500/10 border-rose-500/30 text-rose-400' :
                              m.priority === 'HIGH' ? 'bg-amber-500/10 border-amber-500/30 text-amber-400' :
                              'bg-zinc-800 border-zinc-700 text-zinc-400'}`}
                          >
                            {m.priority}
                          </span>
                        </div>

                        {/* Progress meter bar */}
                        <div className="space-y-1">
                          <div className="flex justify-between font-mono text-[8px] text-zinc-500 uppercase tracking-widest">
                            <span>PROGRESS: {Math.round(m.progress)}%</span>
                            <span className="text-cyan-glow font-bold">{m.status}</span>
                          </div>
                          <div className="h-1.5 w-full bg-zinc-900 rounded-full overflow-hidden border border-zinc-850">
                            <div
                              className={`h-full transition-all duration-300 rounded-full
                                ${m.status === 'COMPLETED' ? 'bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]' :
                                  m.status === 'FAILED' ? 'bg-rose-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]' :
                                  m.status === 'RUNNING' ? 'bg-cyan-glow shadow-[0_0_8px_rgba(0,242,254,0.55)] animate-pulse' :
                                  'bg-zinc-700'}`}
                              style={{ width: `${m.progress}%` }}
                            />
                          </div>
                        </div>

                        {/* Expanded details */}
                        <div className="flex items-center justify-between text-[9px] font-mono pt-1">
                          <button
                            onClick={() => setExpandedMissionId(expandedMissionId === m.id ? null : m.id)}
                            className="text-zinc-500 hover:text-cyan-glow font-bold transition-colors cursor-pointer uppercase tracking-widest text-[8px]"
                          >
                            {expandedMissionId === m.id ? '[- CLOSE LOG]' : '[+ OPEN LOG]'}
                          </button>

                          {/* Control actions */}
                          <div className="flex items-center gap-1.5">
                            {m.status === 'PENDING' && (
                              <button
                                onClick={() => handleStartMission(m.id)}
                                className="p-1 hover:bg-cyan-dim rounded text-cyan-glow hover:text-cyan-glow transition-all cursor-pointer"
                                title="Execute Mission"
                              >
                                <Play className="w-3 h-3" />
                              </button>
                            )}
                            {m.status === 'RUNNING' && (
                              <>
                                <button
                                  onClick={() => handlePauseMission(m.id)}
                                  className="p-1 hover:bg-amber-500/10 rounded text-amber-400 cursor-pointer"
                                  title="Pause"
                                >
                                  <Pause className="w-3 h-3" />
                                </button>
                                <button
                                  onClick={() => handleCancelMission(m.id)}
                                  className="p-1 hover:bg-rose-500/10 rounded text-rose-400 cursor-pointer"
                                  title="Cancel Process"
                                >
                                  <Square className="w-3 h-3" />
                                </button>
                              </>
                            )}
                            {(m.status as string) === 'PAUSED' && (
                              <>
                                <button
                                  onClick={() => handleStartMission(m.id)} // Starts/resumes
                                  className="p-1 hover:bg-cyan-dim rounded text-cyan-glow cursor-pointer"
                                  title="Resume"
                                >
                                  <Play className="w-3 h-3" />
                                </button>
                                <button
                                  onClick={() => handleCancelMission(m.id)}
                                  className="p-1 hover:bg-rose-500/10 rounded text-rose-400 cursor-pointer"
                                  title="Cancel Process"
                                >
                                  <Square className="w-3 h-3" />
                                </button>
                              </>
                            )}
                          </div>
                        </div>

                        {/* Mission detailed logs */}
                        {expandedMissionId === m.id && (
                          <div className="mt-2.5 bg-black/60 border border-matte-border/60 rounded-lg p-2.5 font-mono text-[8px] text-zinc-400 max-h-[140px] overflow-y-auto select-text scrollbar-thin space-y-1">
                            <div className="text-zinc-650 uppercase border-b border-matte-border/20 pb-1 mb-1 tracking-widest text-[7.5px]">
                              KERNEL PROCESS THREAD: {m.id.substring(0, 8)}
                            </div>
                            {m.currentStep && (
                              <div className="text-cyan-glow font-bold uppercase">
                                CURRENT STEP: {m.currentStep}
                              </div>
                            )}
                            {m.currentTool && (
                              <div className="text-amber-400 uppercase">
                                EXEC TOOL: {m.currentTool}
                              </div>
                            )}
                            {m.logs && m.logs.length > 0 ? (
                              <div className="space-y-0.5 pt-1.5 border-t border-matte-border/20 mt-1">
                                {m.logs.map((log, idx) => (
                                  <div key={idx} className="flex gap-1.5">
                                    <span className="text-zinc-650">{log.time}</span>
                                    <span className={`font-semibold
                                      ${log.level === 'SUCCESS' ? 'text-emerald-400' :
                                        log.level === 'WARN' ? 'text-amber-400' :
                                        log.level === 'ERROR' ? 'text-rose-400' :
                                        'text-zinc-400'}`}
                                    >
                                      [{log.level}]
                                    </span>
                                    <span className="break-all">{log.msg}</span>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <div className="text-zinc-650 italic">No executing logs logged.</div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Tab 1b: Running Workflow nodes timeline */}
                {currentWorkflow && workflowNodes.length > 0 && (
                  <div className="mt-6 space-y-3">
                    <div className="flex items-center justify-between font-mono text-[9px] text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-2">
                      <span>Workflow Run Timeline</span>
                      <span className="text-cyan-glow font-bold">{currentWorkflow.status}</span>
                    </div>
                    <div className="bg-black/20 p-3 rounded-xl border border-matte-border/40 space-y-2">
                      <div className="flex justify-between items-center text-[9px] font-mono text-zinc-400 border-b border-matte-border/20 pb-1.5 mb-1.5">
                        <span className="font-bold text-zinc-300 truncate uppercase">{currentWorkflow.name || 'Active Sequence'}</span>
                        <Workflow className="w-3.5 h-3.5 text-cyan-glow animate-pulse" />
                      </div>
                      <div className="space-y-2.5 pl-2 border-l-2 border-matte-border/50">
                        {workflowNodes.map((node) => (
                          <div key={node.id} className="relative flex items-start gap-2.5 text-[9px] font-mono">
                            <span className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0
                              ${node.status === 'COMPLETED' ? 'bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]' :
                                node.status === 'RUNNING' ? 'bg-cyan-glow shadow-[0_0_6px_rgba(0,242,254,0.5)] animate-pulse' :
                                node.status === 'FAILED' ? 'bg-rose-500 shadow-[0_0_6px_rgba(239,68,68,0.5)]' :
                                'bg-zinc-700'}`}
                            />
                            <div className="flex-1 min-w-0">
                              <div className="flex justify-between font-bold text-zinc-300">
                                <span className="truncate">{node.name}</span>
                                <span className="text-zinc-550 text-[8px] uppercase">{node.status}</span>
                              </div>
                              {node.error && <p className="text-rose-400 text-[8px] mt-0.5 break-all leading-normal">{node.error}</p>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tab 1.5: Desktop tab */}
            {activeTab === 'desktop' && (
              <div className="space-y-4 font-mono text-[9px]">
                
                {/* Section A: Telemetry Metrics */}
                <div className="flex items-center justify-between text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-2 flex-shrink-0">
                  <span>DESKTOP OPERATING ENGINE</span>
                  <span className={`font-bold px-1.5 py-0.5 rounded border text-[8px] uppercase
                    ${(telemetryState.queue_length ?? 0) > 0 ? 'bg-cyan-glow/10 border-cyan-glow/30 text-cyan-glow animate-pulse' : 'bg-zinc-800 border-zinc-700 text-zinc-400'}`}
                  >
                    {(telemetryState.queue_length ?? 0) > 0 ? 'AUTOMATION RUNNING' : 'STANDBY'}
                  </span>
                </div>

                <div className="bg-black/25 border border-matte-border/40 rounded-xl p-3 space-y-2.5">
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-550">CURRENT TASK ID:</span>
                    <span className="text-cyan-glow font-bold truncate max-w-[130px]">{telemetryState.current_desktop_task || 'None'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-550">LAST EXECUTED ACTION:</span>
                    <span className="text-zinc-300 truncate max-w-[130px]">{telemetryState.last_executed_action || 'None'}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-550">IN-FLIGHT QUEUE:</span>
                    <span className="text-zinc-300">{(telemetryState.queue_length ?? 0)} actions pending</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-550">AVG RESPONSE TIME:</span>
                    <span className="text-zinc-300">{telemetryState.average_execution_time_ms}ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-zinc-550">PROCESS FAILURES:</span>
                    <span className={`font-bold ${(telemetryState.failure_count ?? 0) > 0 ? 'text-rose-400' : 'text-zinc-400'}`}>
                      {(telemetryState.failure_count ?? 0)} errors logged
                    </span>
                  </div>
                </div>

                {/* Section B: Quick Launch Control Center */}
                <div className="space-y-2">
                  <div className="text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-1">
                    System Control Center
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button
                      type="button"
                      onClick={() => handleQuickAction('take screenshot')}
                      className="bg-black/35 hover:bg-cyan-dim/5 border border-matte-border/40 hover:border-cyan-border/20 text-zinc-300 hover:text-cyan-glow flex items-center justify-start gap-2 text-[9px] font-mono p-2.5 h-10 w-full transition-all cursor-pointer"
                      variant="outline"
                    >
                      <Camera className="w-4 h-4 text-cyan-glow" />
                      <span>Take Screenshot</span>
                    </Button>
                    <Button
                      type="button"
                      onClick={() => handleQuickAction('read clipboard contents')}
                      className="bg-black/35 hover:bg-cyan-dim/5 border border-matte-border/40 hover:border-cyan-border/20 text-zinc-300 hover:text-cyan-glow flex items-center justify-start gap-2 text-[9px] font-mono p-2.5 h-10 w-full transition-all cursor-pointer"
                      variant="outline"
                    >
                      <ClipboardCopy className="w-4 h-4 text-cyan-glow" />
                      <span>Sync Clipboard</span>
                    </Button>
                  </div>
                </div>

                {/* Section C: Desktop App Launcher */}
                <div className="space-y-2">
                  <div className="text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-1">
                    Process Controller Launcher
                  </div>
                  <div className="space-y-2">
                    {[
                      { name: 'Google Chrome', proc: 'google-chrome' },
                      { name: 'VS Code Editor', proc: 'code' },
                      { name: 'System Terminal', proc: 'gnome-terminal' },
                    ].map((app, idx) => (
                      <div key={idx} className="flex justify-between items-center p-2.5 bg-black/25 border border-matte-border/40 rounded-xl">
                        <div className="flex flex-col gap-0.5 max-w-[120px] overflow-hidden">
                          <span className="text-zinc-300 font-bold truncate">{app.name}</span>
                          <span className="text-zinc-550 text-[8px] truncate">BINARY: {app.proc}</span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={() => handleQuickAction(`open application ${app.proc}`)}
                            className="px-2 py-1 bg-cyan-dim/10 border border-cyan-border/25 hover:bg-cyan-glow hover:text-black text-cyan-glow text-[8px] font-bold rounded transition-all cursor-pointer uppercase font-mono"
                          >
                            Launch
                          </button>
                          <button
                            type="button"
                            onClick={() => handleQuickAction(`close application ${app.proc}`)}
                            className="px-2 py-1 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500 hover:text-white text-rose-400 text-[8px] font-bold rounded transition-all cursor-pointer uppercase font-mono"
                          >
                            Kill
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Section D: Notification Feed */}
                <div className="space-y-2">
                  <div className="text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-1">
                    Smart Notification Monitor
                  </div>
                  <div className="bg-black/40 border border-matte-border/60 rounded-xl p-2.5 max-h-[140px] overflow-y-auto scrollbar-thin space-y-2 select-text text-[8px]">
                    {[
                      { title: 'Screen Capture Completed', body: 'Screenshot saved to kernel workspace assets.', time: '02:44:10', type: 'success' },
                      { title: 'Subsystem Connection Verified', body: 'Verified socket bridge under ws://localhost:8000/ws/voice.', time: '02:43:08', type: 'info' },
                      { title: 'Permissions Synced', body: 'Acquired write_file permission validation scope.', time: '02:42:01', type: 'success' },
                    ].map((n, idx) => (
                      <div key={idx} className="border-b border-matte-border/20 pb-2 last:border-none last:pb-0 space-y-0.5">
                        <div className="flex justify-between items-center font-bold text-zinc-300 uppercase text-[8px]">
                          <span className={n.type === 'success' ? 'text-emerald-400' : 'text-cyan-glow'}>{n.title}</span>
                          <span className="text-zinc-550 text-[7px]">{n.time}</span>
                        </div>
                        <p className="text-zinc-500 leading-relaxed text-[7.5px] uppercase">{n.body}</p>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            )}

            {/* Tab 2: Memory store & Search */}
            {activeTab === 'memory' && (
              <div className="space-y-4">
                <div className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-2 flex-jestify-between items-center">
                  <span>LONG TERM MEMORY COLLECTIONS</span>
                  <span className="text-cyan-glow font-bold">2 active</span>
                </div>

                {/* Collections lists */}
                <div className="space-y-2.5 font-mono text-[9px]">
                  {[
                    { name: 'friday-core-docs', items: '4,212', status: 'ACTIVE' },
                    { name: 'project-friday-code', items: '12,940', status: 'ACTIVE' }
                  ].map((store, idx) => (
                    <div key={idx} className="flex justify-between items-center p-2.5 bg-black/25 border border-matte-border/40 rounded-xl">
                      <div className="flex flex-col gap-0.5">
                        <span className="text-cyan-glow font-bold">{store.name}</span>
                        <span className="text-zinc-550 text-[8px]">{store.items} EMBEDDING NODES</span>
                      </div>
                      <span className="text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20 text-[8px] font-bold">
                        {store.status}
                      </span>
                    </div>
                  ))}
                </div>

                {/* Semantic Query tool */}
                <form onSubmit={handleMemorySearch} className="space-y-2 pt-2.5 border-t border-matte-border/20">
                  <div className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest flex justify-between items-center">
                    <span>SEMANTIC CONTEXT QUERY</span>
                    <span className="text-zinc-650 text-[8px]">PRESS [⌘K] TO FOCUS</span>
                  </div>
                  <div className="flex gap-2">
                    <Input
                      id="memory-search-input"
                      value={memoryQuery}
                      onChange={(e) => setMemoryQuery(e.target.value)}
                      placeholder="Query workspace embeddings..."
                      className="h-8 py-0 px-2 font-mono text-[10px]"
                    />
                    <Button type="submit" size="sm" className="h-8 font-mono text-[10px] tracking-wider px-3.5 cursor-pointer">
                      Query
                    </Button>
                  </div>
                </form>

                {/* Query Results */}
                <div className="space-y-2">
                  {searchResults && searchResults.length > 0 ? (
                    <>
                      <div className="font-mono text-[9px] text-zinc-500 uppercase tracking-widest">
                        SEMANTIC SEARCH MATCHES
                      </div>
                      <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1.5 scrollbar-thin">
                        {searchResults.map((res) => (
                          <div key={res.id} className="p-2.5 bg-black/35 border border-matte-border/40 rounded-xl space-y-1 font-mono text-[9px]">
                            <div className="flex justify-between text-[8px] text-zinc-400">
                              <span className="truncate max-w-[150px] font-bold text-cyan-glow uppercase">
                                {res.metadata.file_path.split('/').pop()}
                              </span>
                              <span className="text-cyan-glow font-semibold">
                                {Math.round(res.score * 100)}% Match
                              </span>
                            </div>
                            <p className="text-zinc-500 text-[8px] truncate italic">
                              PATH: {res.metadata.file_path}
                            </p>
                            <p className="text-zinc-355 text-[8.5px] leading-relaxed break-words bg-black/20 p-1.5 rounded border border-matte-border/20 line-clamp-3">
                              {res.document}
                            </p>
                          </div>
                        ))}
                      </div>
                    </>
                  ) : memoryQuery && (
                    <div className="text-center py-6 font-mono text-[8px] text-zinc-600 uppercase tracking-widest">
                      NO MATCHING SEMANTIC VECTORS
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Tab 3: System Health console */}
            {activeTab === 'system' && (
              <div className="space-y-4 font-mono text-[9px]">
                <div className="text-zinc-550 uppercase tracking-widest border-b border-matte-border/20 pb-2">
                  HARDWARE ENVIRONMENT STATUS
                </div>

                <div className="space-y-2 bg-black/25 border border-matte-border/40 rounded-xl p-3">
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-500">CPU UTILIZATION:</span>
                    <span className="text-cyan-glow font-bold">{kernelState.cpuUtilization}%</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-500">MEMORY ALLOCATED:</span>
                    <span className="text-zinc-350">{((kernelState.memoryUsageBytes || 0) / (1024 * 1024)).toFixed(1)} MB</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-500">SYSTEM UPTIME:</span>
                    <span className="text-zinc-350">{kernelState.uptime}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-matte-border/20">
                    <span className="text-zinc-500">REGISTERED MODULES:</span>
                    <span className="text-zinc-300">{kernelState.registeredServicesCount} modules</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-zinc-500">MODEL PROVIDER:</span>
                    <span className="text-zinc-350 uppercase">GEMINI-1.5-FLASH</span>
                  </div>
                </div>

                {/* Subsystem health grid */}
                <div className="space-y-2">
                  <div className="text-zinc-500 uppercase tracking-widest border-b border-matte-border/20 pb-1 mb-1.5">
                    Subsystem Diagnostics Grid
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {healthState.services.map((srv, idx) => (
                      <div key={idx} className="p-2 bg-black/35 border border-matte-border/40 rounded-lg flex flex-col items-center justify-center text-center font-mono text-[8px] gap-1">
                        <span className="text-zinc-400 font-bold uppercase truncate w-full">{srv.name}</span>
                        <span className={`font-semibold text-[7.5px] px-1 rounded uppercase
                          ${srv.status === 'HEALTHY' ? 'bg-emerald-500/10 text-emerald-400' :
                            srv.status === 'WARNING' ? 'bg-amber-500/10 text-amber-400 animate-pulse' :
                            'bg-zinc-800 text-zinc-550'}`}
                        >
                          {srv.status === 'HEALTHY' ? 'OK' : srv.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Token stats */}
                {telemetryState.eventsCount > 0 && (
                  <div className="space-y-2 bg-black/25 border border-matte-border/40 rounded-xl p-3">
                    <div className="text-zinc-500 uppercase tracking-wider text-[8px] mb-1.5 border-b border-matte-border/20 pb-1">
                      SESSION STREAM TELEMETRY
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-555">PROCESSED TELEMETRY EVENTS:</span>
                      <span className="text-zinc-300">{telemetryState.eventsCount}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-555">ACTIVE AGENT WORKFLOW:</span>
                      <span className="text-zinc-300 truncate max-w-[120px]">{telemetryState.workflow || 'None'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-555">EXECUTION TIME:</span>
                      <span className="text-zinc-300">{telemetryState.executionTimeMs}ms</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-555">WORKSPACE LATENCY:</span>
                      <span className="text-zinc-300">{telemetryState.latency}ms</span>
                    </div>
                    <div className="flex justify-between font-bold text-cyan-glow">
                      <span>AVERAGE CALL DURATION:</span>
                      <span>{telemetryState.average_execution_time_ms || 0}ms</span>
                    </div>
                  </div>
                )}

                {/* Raw kernel logs */}
                <div className="space-y-2">
                  <div className="text-zinc-550 uppercase tracking-widest border-b border-matte-border/20 pb-1 mb-1.5">
                    KERNEL LOGGER
                  </div>
                  <div className="bg-black/60 border border-matte-border/60 rounded-xl p-2.5 max-h-[160px] overflow-y-auto scrollbar-thin space-y-1.5 select-text text-[8px] leading-relaxed">
                    {logs.slice(-15).map((log) => (
                      <div key={log.id} className="flex gap-1.5">
                        <span className="text-zinc-650 flex-shrink-0">{log.timestamp}</span>
                        <span className={`font-semibold flex-shrink-0
                          ${log.type === 'success' ? 'text-emerald-400' :
                            log.type === 'warn' ? 'text-amber-400' :
                            log.type === 'error' ? 'text-rose-400' :
                            'text-cyan-glow/70'}`}
                        >
                          [{log.type.toUpperCase()}]
                        </span>
                        <span className="text-zinc-350 break-all">{log.message}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

          </div>
        </Card>
      </div>

    </div>
  );
};
