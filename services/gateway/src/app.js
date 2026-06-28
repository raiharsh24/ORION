import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import cookieParser from 'cookie-parser';
import morgan from 'morgan';
import { config } from './config/index.js';
import { errorHandler } from './middleware/errorMiddleware.js';
import { limiter } from './middleware/rateLimiter.js';
import apiRouter from './routes/index.js';
import { pythonProxy } from './middleware/proxyMiddleware.js';

const app = express();

// Secure application with standard Helmet headers
app.use(helmet());

// Enable Cross-Origin Resource Sharing with configured desktop host
app.use(cors({
  origin: config.corsOrigin,
  credentials: true
}));

// Apply response body compression
app.use(compression());

// Parse requests
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());

// Request logger middleware
if (config.nodeEnv === 'development') {
  app.use(morgan('dev'));
} else {
  app.use(morgan('combined'));
}

// Apply rate limiter to all API endpoints BEFORE route registrations
app.use('/api', limiter);

// ---------------- Public Endpoints ----------------

// GET /health
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// GET /status
app.get('/status', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'gateway',
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

// ---------------- Proxy Endpoints (Targeting Python Core) ----------------
app.use(['/ask', '/api/ask'], pythonProxy());
app.use(['/kernel', '/api/kernel'], pythonProxy());
app.use(['/missions', '/api/missions'], pythonProxy());
app.use(['/telemetry', '/api/telemetry'], pythonProxy());
app.use(['/workflows', '/api/workflows'], pythonProxy());
app.use(['/workspace', '/api/workspace'], pythonProxy());
app.use(['/knowledge', '/api/knowledge'], pythonProxy());
app.use(['/events', '/api/events'], pythonProxy());
app.use(['/ws', '/api/ws', '/ws/voice'], pythonProxy());

// ---------------- API Endpoints ----------------

// Register API routes at both root and /api paths for total client flexibility
app.use('/api', apiRouter);
app.use('/', apiRouter);

// 404 fallthrough handler at the bottom
app.use((req, res, next) => {
  res.status(404).json({
    success: false,
    error: "API resource not found."
  });
});

// Global unhandled error handler middleware
app.use(errorHandler);

export default app;
