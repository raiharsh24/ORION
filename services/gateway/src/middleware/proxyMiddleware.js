import { createProxyMiddleware } from 'http-proxy-middleware';

const targets = [
  '/ask', '/api/ask',
  '/chat', '/api/chat',
  '/chat/stream', '/api/chat/stream',
  '/kernel', '/api/kernel',
  '/missions', '/api/missions',
  '/telemetry', '/api/telemetry',
  '/workflows', '/api/workflows',
  '/workspace', '/api/workspace',
  '/knowledge', '/api/knowledge',
  '/events', '/api/events',
  '/ws', '/api/ws', '/ws/voice',
  '/cognitive', '/api/cognitive',
  '/readiness', '/api/readiness',
  '/ready', '/api/ready',
  '/live', '/api/live',
  '/health', '/api/health',
  '/version', '/api/version',
  '/metrics', '/api/metrics',
  '/vision', '/api/vision',
  '/atlas', '/api/atlas',
  '/runtime_missions', '/api/runtime_missions',
  '/workflow_runtime', '/api/workflow_runtime',
  '/memory_inspector', '/api/memory_inspector',
  '/planner_inspector', '/api/planner_inspector',
  '/runtime_inspector', '/api/runtime_inspector',
  '/agent_inspector', '/api/agent_inspector',
  '/cognitive_inspector', '/api/cognitive_inspector'
];

const proxyFilter = (pathname) => {
  return targets.some(target => pathname === target || pathname.startsWith(target + '/'));
};

/**
 * Creates an Express reverse proxy handler targeting the Python FastAPI core backend.
 * @param {string} targetUrl - Python core service target URL.
 * @returns {Function} Express middleware.
 */
export const pythonProxy = (targetUrl = process.env.KERNEL_URL || 'http://localhost:8000') => {
  return createProxyMiddleware({
    target: targetUrl,
    changeOrigin: true,
    pathFilter: proxyFilter
  });
};
