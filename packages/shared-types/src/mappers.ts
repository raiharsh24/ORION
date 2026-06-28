import { OrionResponse, TelemetrySnapshot, Session } from './index';

export function mapResponseToTelemetry(res: OrionResponse): TelemetrySnapshot {
  return {
    model: res.model || '',
    provider: res.provider || '',
    promptTokens: res.usage?.promptTokens || 0,
    completionTokens: res.usage?.completionTokens || 0,
    totalTokens: res.usage?.totalTokens || 0,
    executionTimeMs: res.metadata?.executionTimeMs || 0,
    intentClassification: res.metadata?.intentClassification || 'CHAT',
    toolsExecuted: res.metadata?.toolsExecuted || 'NONE'
  };
}

export function mapSnakeToCamelSession(raw: Record<string, any>): Session {
  return {
    id: String(raw.session_id || ''),
    createdAt: typeof raw.created_at === 'number' ? raw.created_at : Math.floor(new Date(raw.created_at || Date.now()).getTime() / 1000),
    updatedAt: typeof raw.updated_at === 'number' ? raw.updated_at : Math.floor(new Date(raw.updated_at || Date.now()).getTime() / 1000),
    provider: String(raw.provider || 'gemini'),
    model: String(raw.model || 'gemini-2.5-flash'),
    messageCount: Array.isArray(raw.messages) ? raw.messages.length : 0,
    summary: raw.summary || 'Active Session',
    context: raw.context || 'nominal',
    tool_used: raw.tool_used || null,
    tool_output: raw.tool_output || null
  };
}
