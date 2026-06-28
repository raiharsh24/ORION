import { createProxyMiddleware } from 'http-proxy-middleware';

/**
 * Creates an Express reverse proxy handler targeting the Python FastAPI core backend.
 * @param {string} targetUrl - Python core service target URL.
 * @returns {Function} Express middleware.
 */
export const pythonProxy = (targetUrl = process.env.KERNEL_URL || 'http://localhost:8000') => {
  return createProxyMiddleware({
    target: targetUrl,
    changeOrigin: true,
  });
};
