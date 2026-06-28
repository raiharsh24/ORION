import { engine } from '../engine.js';
import { StreamManager } from '../../../../src/ai/response/index.js';

const streamManager = new StreamManager();

/**
 * Controller to process a standard or streaming chat conversation.
 */
export const chatController = async (req, res, next) => {
  let isStream = false;
  let abortController = null;
  try {
    const { message, prompt, sessionId, session_id, stream } = req.body;
    isStream = stream === true;
    
    // Support both prompt/message and sessionId/session_id for client compatibility
    const activeMessage = prompt || message;
    const activeSessionId = session_id || sessionId;

    if (!activeMessage || typeof activeMessage !== 'string') {
      return res.status(400).json({
        success: false,
        error: "Required string parameter 'message' or 'prompt' is missing."
      });
    }

    if (!activeSessionId || typeof activeSessionId !== 'string') {
      return res.status(400).json({
        success: false,
        error: "Required string parameter 'sessionId' or 'session_id' is missing."
      });
    }

    // Stream handler logic if requested by client
    if (isStream) {
      abortController = new AbortController();
      req.on('close', () => {
        abortController.abort();
      });

      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.setHeader('X-Accel-Buffering', 'no');

      const streamSource = await engine.streamChat(activeSessionId, activeMessage, null, {
        signal: abortController.signal
      });

      await streamManager.handleStream(streamSource, {
        onChunk: (chunkText, chunkEnvelope) => {
          if (abortController.signal.aborted) return;
          res.write(`data: ${JSON.stringify(chunkEnvelope)}\n\n`);
        },
        onComplete: (finalEnvelope) => {
          if (abortController.signal.aborted) return;
          res.write(`data: ${JSON.stringify(finalEnvelope)}\n\n`);
          res.write(`data: ${JSON.stringify({ done: true })}\n\n`);
          res.end();
        },
        onError: (errorEnvelope) => {
          if (abortController.signal.aborted) return;
          res.write(`data: ${JSON.stringify(errorEnvelope)}\n\n`);
          res.end();
        }
      });
      return;
    }

    // Call FridayEngine's standard chat workflow
    abortController = new AbortController();
    req.on('close', () => {
      abortController.abort();
    });
    const response = await engine.chat(activeSessionId, activeMessage, null, {
      signal: abortController.signal
    });
    
    return res.status(response.success ? 200 : 500).json(response);
  } catch (error) {
    if (error.name === 'AbortError' || (abortController && abortController.signal.aborted)) {
      res.end();
      return;
    }

    if (isStream && res.headersSent) {
      res.write(`data: ${JSON.stringify({ success: false, error: error.message })}\n\n`);
      res.end();
    } else {
      next(error);
    }
  }
};

/**
 * Controller to handle Server-Sent Events (SSE) chat streams using FridayEngine on /chat/stream.
 */
export const streamChatController = async (req, res, next) => {
  let abortController = null;
  try {
    const { message, prompt, sessionId, session_id } = req.body;
    abortController = new AbortController();
    req.on('close', () => {
      abortController.abort();
    });

    const activeMessage = prompt || message;
    const activeSessionId = session_id || sessionId;

    if (!activeMessage || typeof activeMessage !== 'string') {
      return res.status(400).json({
        success: false,
        error: "Required string parameter 'message' or 'prompt' is missing."
      });
    }

    if (!activeSessionId || typeof activeSessionId !== 'string') {
      return res.status(400).json({
        success: false,
        error: "Required string parameter 'sessionId' or 'session_id' is missing."
      });
    }

    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');

    const streamSource = await engine.streamChat(activeSessionId, activeMessage, null, {
      signal: abortController.signal
    });

    await streamManager.handleStream(streamSource, {
      onChunk: (chunkText, chunkEnvelope) => {
        if (abortController.signal.aborted) return;
        res.write(`data: ${JSON.stringify(chunkEnvelope)}\n\n`);
      },
      onComplete: (finalEnvelope) => {
        if (abortController.signal.aborted) return;
        res.write(`data: ${JSON.stringify(finalEnvelope)}\n\n`);
        res.write(`data: ${JSON.stringify({ done: true })}\n\n`);
        res.end();
      },
      onError: (errorEnvelope) => {
        if (abortController.signal.aborted) return;
        res.write(`data: ${JSON.stringify(errorEnvelope)}\n\n`);
        res.end();
      }
    });

  } catch (error) {
    if (error.name === 'AbortError' || (abortController && abortController.signal.aborted)) {
      res.end();
      return;
    }

    if (res.headersSent) {
      res.write(`data: ${JSON.stringify({ success: false, error: error.message })}\n\n`);
      res.end();
    } else {
      next(error);
    }
  }
};
