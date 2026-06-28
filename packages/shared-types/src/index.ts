export type MessageRole = 'user' | 'assistant' | 'system';

export interface ChatMessage {
  id?: string;
  role: MessageRole;
  content: string;
  timestamp: number;
  sessionId?: string;
}

export interface ChatRequest {
  prompt: string;
  session_id: string;
  stream?: boolean;
}

export interface Session {
  id: string;
  createdAt: number;
  updatedAt: number;
  provider: string;
  model: string;
  messageCount: number;
  summary?: string;
  context?: string;
  tool_used?: string | null;
  tool_output?: string | null;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface OrionResponse {
  success: boolean;
  provider: string;
  model: string;
  response: string;
  usage: TokenUsage;
  metadata: {
    sessionId: string;
    executionTimeMs: number;
    intentClassification?: string;
    toolsExecuted?: string;
  };
}

export interface StreamChunk {
  text?: string;
  done: boolean;
  error?: string;
  usage?: TokenUsage;
}

export interface ToolExecutionRequest {
  tool_name: string;
  args: Record<string, unknown>;
  confirmed?: boolean;
  confirmation_token?: string;
}

export interface ToolExecutionResult {
  tool_name: string;
  success: boolean;
  output: string;
  error?: string;
  requires_confirmation?: boolean;
  confirmation_token?: string;
}

export interface TelemetrySnapshot {
  model: string;
  provider: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  executionTimeMs: number;
  intentClassification: string;
  toolsExecuted: string;
}
