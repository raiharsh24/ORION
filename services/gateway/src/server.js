import http from 'http';
import { createProxyMiddleware } from 'http-proxy-middleware';
import app from './app.js';
import { config } from './config/index.js';

const wsProxy = createProxyMiddleware({
  target: process.env.KERNEL_URL || 'http://localhost:8000',
  changeOrigin: true,
  ws: true,
});

const server = http.createServer(app);

server.on('upgrade', (req, socket, head) => {
  wsProxy.upgrade(req, socket, head);
});

server.listen(config.port, () => {
  console.log(`Gateway Service listening on port ${config.port} in [${config.nodeEnv}] mode`);
});
