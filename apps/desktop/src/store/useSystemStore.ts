import { create } from 'zustand';
import { API_BASE_URL } from '../config/api';

let currentAbortController: AbortController | null = null;

export interface SystemLog {
  id: string;
  timestamp: string;
  type: 'info' | 'success' | 'warn' | 'error';
  message: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatSession {
  session_id: string;
  messages: ChatMessage[];
  created_at: number;
  summary: string;
  context: string;
  tool_used?: string | null;
  tool_output?: string | null;
}

export interface TelemetryDetail {
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  error?: string | null;
}

export interface ProjectDetail {
  name: string;
  path: string;
  is_git: boolean;
  branch: string | null;
  files_count: number;
  languages: string[];
}

export interface SearchResultDetail {
  id: string;
  document: string;
  metadata: {
    file_path: string;
    project_name: string;
    file_type: string;
    chunk_index: number;
  };
  score: number;
}

interface SystemState {
  sidebarOpen: boolean;
  user: {
    name: string;
    role: string;
  };
  systemStatus: 'nominal' | 'loading' | 'degraded' | 'offline';
  logs: SystemLog[];
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  addLog: (message: string, type?: SystemLog['type']) => void;
  clearLogs: () => void;
  setSystemStatus: (status: SystemState['systemStatus']) => void;

  // Core API integration states
  sessions: ChatSession[];
  currentSessionId: string | null;
  chatMessages: ChatMessage[];
  streamingMessage: string | null;
  apiConnected: boolean;
  lastTelemetry: TelemetryDetail | null;
  lastExecutionTimeMs: number | null;
  lastIntent: string | null;
  lastToolUsed: string | null;

  // Confirmation loop state
  pendingConfirmation: { prompt: string; token: string; toolName: string } | null;

  // Alpha 1.2 Knowledge states
  workspaceProjects: ProjectDetail[];
  indexingInProgress: boolean;
  searchResults: SearchResultDetail[];

  // API Actions
  checkBackendStatus: () => Promise<void>;
  fetchSessions: () => Promise<void>;
  setSession: (sessionId: string) => Promise<void>;
  sendMessageStream: (prompt: string, confirmed?: boolean, confirmationToken?: string | null) => Promise<void>;
  confirmPendingAction: () => Promise<void>;
  cancelPendingAction: () => void;
  cancelCurrentRequest: () => void;
  createNewSession: () => void;

  // Knowledge Engine Actions
  fetchWorkspaceProjects: () => Promise<void>;
  triggerIndexing: (path?: string, projectName?: string) => Promise<void>;
  performKnowledgeSearch: (query: string) => Promise<void>;
}

export const useSystemStore = create<SystemState>((set, get) => ({
  sidebarOpen: true,
  user: {
    name: 'Harsh',
    role: 'Lead Frontend Engineer',
  },
  systemStatus: 'nominal',
  logs: [
    { id: '1', timestamp: '12:05:29', type: 'info', message: 'FRIDAY Kernel loaded successfully.' },
    { id: '2', timestamp: '12:05:30', type: 'success', message: 'Neural network client synchronized.' },
    { id: '3', timestamp: '12:05:32', type: 'info', message: 'Security handshake complete.' },
  ],
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  addLog: (message, type = 'info') => set((state) => {
    const newLog: SystemLog = {
      id: Math.random().toString(36).substring(2, 9),
      timestamp: new Date().toLocaleTimeString('en-US', { hour12: false }),
      type,
      message,
    };
    return { logs: [...state.logs.slice(-49), newLog] }; // Keep last 50 logs
  }),
  clearLogs: () => set({ logs: [] }),
  setSystemStatus: (status) => set({ systemStatus: status }),

  // API Integrations
  sessions: [],
  currentSessionId: null,
  chatMessages: [],
  streamingMessage: null,
  apiConnected: false,
  lastTelemetry: null,
  lastExecutionTimeMs: null,
  lastIntent: null,
  lastToolUsed: null,
  pendingConfirmation: null,

  // Knowledge defaults
  workspaceProjects: [],
  indexingInProgress: false,
  searchResults: [],

  checkBackendStatus: async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/health`);
      if (res.ok) {
        set({ 
          apiConnected: true, 
          systemStatus: 'nominal' 
        });
      } else {
        set({ apiConnected: false, systemStatus: 'offline' });
      }
    } catch {
      set({ apiConnected: false, systemStatus: 'offline' });
    }
  },

  fetchSessions: async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/sessions`);
      if (res.ok) {
        const data = await res.json();
        set({ sessions: data });
      }
    } catch (e) {
      console.error("Failed to query sessions list:", e);
    }
  },

  setSession: async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        set({
          currentSessionId: sessionId,
          chatMessages: data.messages || [],
          streamingMessage: null,
          lastIntent: data.context?.replace("Intent: ", "") || "CHAT",
          lastToolUsed: data.tool_used || null,
          lastExecutionTimeMs: null,
          lastTelemetry: null
        });
      }
    } catch (e) {
      console.error("Failed to fetch session details:", e);
    }
  },

  sendMessageStream: async (prompt: string, confirmed = false, confirmationToken = null) => {
    const { currentSessionId, addLog, checkBackendStatus } = get();
    await checkBackendStatus();
    
    const sessionId = currentSessionId || Math.random().toString(36).substring(2, 15);
    
    // Log user prompt message locally if not confirming a prompt we already typed
    if (!confirmed) {
      const userMsg: ChatMessage = {
        role: 'user',
        content: prompt,
        timestamp: Date.now() / 1000
      };

      set((state) => ({
        currentSessionId: sessionId,
        chatMessages: [...state.chatMessages, userMsg],
        streamingMessage: ''
      }));
      addLog(`Posting query payload to stream: "${prompt}"`, 'info');
    } else {
      addLog(`Posting confirmed action execution payload: "${prompt}"`, 'info');
      set({ streamingMessage: '' });
    }

    const startTime = Date.now();
    if (currentAbortController) {
      currentAbortController.abort();
    }
    const abortController = new AbortController();
    currentAbortController = abortController;

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: abortController.signal,
        body: JSON.stringify({
          prompt: prompt,
          session_id: sessionId,
          stream: true,
          confirmed: confirmed,
          confirmation_token: confirmationToken
        })
      });

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const result = await response.json();
        
        if (result.success === false) {
          const assistantMsg: ChatMessage = {
            role: 'assistant',
            content: "FRIDAY:\nUnable to process your request.",
            timestamp: Date.now() / 1000
          };

          set((state) => ({
            chatMessages: [...state.chatMessages, assistantMsg],
            streamingMessage: null,
            lastIntent: result.intent || 'CHAT',
            lastToolUsed: result.tool_used || null,
            lastExecutionTimeMs: result.execution_time_ms || 0
          }));
          addLog(`API error: ${result.error || 'Unknown error'}`, 'error');
          await get().fetchSessions();
          return;
        }

        if (result.confirmation_required) {
          // Destructive action confirmation intercepted
          set({
            pendingConfirmation: {
              prompt: prompt,
              token: result.confirmation_token,
              toolName: result.tool_used
            }
          });

          const assistantText =
            result.response ??
            result.text ??
            result.message ??
            "";

          if (!assistantText) {
            console.warn("No assistant response found", result);
          }

          const assistantMsg: ChatMessage = {
            role: 'assistant',
            content: assistantText,
            timestamp: Date.now() / 1000
          };

          set((state) => ({
            chatMessages: [...state.chatMessages, assistantMsg],
            streamingMessage: null
          }));
          addLog(`Action requires confirmation: ${assistantText}`, 'warn');
          return;
        } else {
          // Flat JSON response fallback (e.g. if stream was skipped)
          const assistantText =
            result.response ??
            result.text ??
            result.message ??
            "";

          if (!assistantText) {
            console.warn("No assistant response found", result);
          }

          const assistantMsg: ChatMessage = {
            role: 'assistant',
            content: assistantText || "No response received.",
            timestamp: Date.now() / 1000
          };

          set((state) => ({
            chatMessages: [...state.chatMessages, assistantMsg],
            streamingMessage: null,
            lastIntent: result.intent || 'CHAT',
            lastToolUsed: result.tool_used || null,
            lastExecutionTimeMs: result.execution_time_ms || 0
          }));

          if (result.tool_used) {
            addLog(`Tool Executed: ${result.tool_used}. Result: ${result.tool_output || 'Success'}`, 'success');
          }
          await get().fetchSessions();
          return;
        }
      }

      if (!response.ok || !response.body) {
        throw new Error(`API HTTP error status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let accumulated = '';
      let buffer = '';
      let streamUsage: TelemetryDetail | null = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.substring(6);
            if (chunk === '[DONE]') continue;
            
            try {
              const parsed = JSON.parse(chunk);
              if (parsed.success === false) {
                accumulated = "FRIDAY:\nUnable to process your request.";
                break;
              }
              
              const assistantText =
                parsed.response ??
                parsed.text ??
                parsed.message ??
                "";
              
              if (parsed.metadata?.streamCompleted) {
                accumulated = assistantText;
                const u = parsed.usage;
                if (u) {
                  streamUsage = {
                    model: parsed.provider || 'gemini-1.5-flash',
                    prompt_tokens: u.promptTokens ?? 0,
                    completion_tokens: u.completionTokens ?? 0,
                    total_tokens: u.totalTokens ?? 0
                  };
                }
              } else {
                accumulated += assistantText;
              }
            } catch (err) {
              console.warn("Failed to parse stream chunk", chunk, err);
              accumulated += chunk;
            }

            set({ streamingMessage: accumulated });
          }
        }
      }

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: accumulated,
        timestamp: Date.now() / 1000
      };

      set((state) => ({
        chatMessages: [...state.chatMessages, assistantMsg],
        streamingMessage: null
      }));

      addLog(`Streaming content completed successfully.`, 'success');
      await get().fetchSessions();

      // Retrieve telemetry metadata summary
      const sessRes = await fetch(`${API_BASE_URL}/sessions/${sessionId}`);
      if (sessRes.ok) {
        const details = await sessRes.json();
        const lastIntent = details.context?.replace("Intent: ", "") || "CHAT";
        const toolUsed = details.tool_used || null;
        const toolOutput = details.tool_output || null;

        set({
          lastIntent,
          lastToolUsed: toolUsed,
          lastExecutionTimeMs: details.execution_time_ms || (Date.now() - startTime),
          lastTelemetry: streamUsage
        });

        if (toolUsed) {
          addLog(`Tool Executed: ${toolUsed}. Result: ${toolOutput || 'Success'}`, 'success');
        }
      }

      currentAbortController = null;
    } catch (err: any) {
      console.error(err);
      addLog(`Streaming connection failed: ${err.message}`, 'error');

      const errMsg: ChatMessage = {
        role: 'assistant',
        content: `Connection error: ${err.message || 'AI Engine API endpoint timed out.'}`,
        timestamp: Date.now() / 1000
      };

      set((state) => ({
        chatMessages: [...state.chatMessages, errMsg],
        streamingMessage: null,
        lastTelemetry: {
          model: 'gemini-1.5-flash',
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        error: err.message
      }
      }));
      currentAbortController = null;
    }
  },

  confirmPendingAction: async () => {
    const { pendingConfirmation, sendMessageStream } = get();
    if (!pendingConfirmation) return;
    const { prompt, token } = pendingConfirmation;
    set({ pendingConfirmation: null });
    await sendMessageStream(prompt, true, token);
  },

  cancelPendingAction: () => {
    const { addLog } = get();
    set({ pendingConfirmation: null });
    addLog("Potentially destructive action cancelled by user.", "warn");
    const cancelMsg: ChatMessage = {
      role: 'assistant',
      content: "Action cancelled.",
      timestamp: Date.now() / 1000
    };
    set((state) => ({
      chatMessages: [...state.chatMessages, cancelMsg]
    }));
  },

  cancelCurrentRequest: () => {
    if (currentAbortController) {
      currentAbortController.abort();
      currentAbortController = null;
    }
  },

  createNewSession: () => {
    set({
      currentSessionId: null,
      chatMessages: [],
      streamingMessage: null,
      lastTelemetry: null,
      lastIntent: null,
      lastToolUsed: null,
      lastExecutionTimeMs: null,
      pendingConfirmation: null
    });
  },

  // ---------- Alpha 1.2 Knowledge Engine Actions ----------

  fetchWorkspaceProjects: async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/workspace/projects`);
      if (res.ok) {
        const data = await res.json();
        set({ workspaceProjects: data });
      }
    } catch (e) {
      console.error("Failed to query workspace projects:", e);
    }
  },

  triggerIndexing: async (path, projectName) => {
    const { addLog } = get();
    set({ indexingInProgress: true });
    addLog(`Initiating document indexer for: ${projectName || 'Default Workspace'}`, 'info');
    try {
      const res = await fetch(`${API_BASE_URL}/knowledge/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, project_name: projectName })
      });
      if (res.ok) {
        const result = await res.json();
        addLog(result.message, 'success');
        await get().fetchWorkspaceProjects();
      } else {
        addLog("Indexer request failed.", "error");
      }
    } catch (err: any) {
      addLog(`Indexing request failed: ${err.message}`, 'error');
    } finally {
      set({ indexingInProgress: false });
    }
  },

  performKnowledgeSearch: async (query) => {
    const { addLog } = get();
    if (!query.trim()) return;
    addLog(`Querying knowledge base for search terms: "${query}"`, 'info');
    try {
      const res = await fetch(`${API_BASE_URL}/knowledge/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, n_results: 5 })
      });
      if (res.ok) {
        const data = await res.json();
        set({ searchResults: data.results || [] });
        addLog(`Query completed: found ${data.results?.length || 0} matches.`, 'success');
      } else {
        addLog("Knowledge search failed.", "error");
      }
    } catch (err: any) {
      addLog(`Knowledge search failed: ${err.message}`, 'error');
    }
  }
}));
