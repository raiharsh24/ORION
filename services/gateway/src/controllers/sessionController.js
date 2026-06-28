import { engine } from '../engine.js';

/**
 * Format a session into the snake_case JSON response expected by the desktop.
 * @param {object} session - ChatSession instance.
 * @param {Array} messages - Chat history message list.
 * @returns {object} JSON session object.
 */
const formatSessionJson = (session, messages = []) => {
  return {
    session_id: session.sessionId,
    messages: messages.map(m => ({
      role: m.role,
      content: m.content,
      timestamp: typeof m.timestamp === 'string' ? Math.floor(new Date(m.timestamp).getTime() / 1000) : m.timestamp
    })),
    // Convert date string/timestamp to Unix timestamp in seconds
    created_at: typeof session.createdAt === 'string' ? Math.floor(new Date(session.createdAt).getTime() / 1000) : session.createdAt,
    summary: session.conversationMetadata?.summary || "Conversation session initialized.",
    context: session.conversationMetadata?.context || "nominal",
    tool_used: session.conversationMetadata?.tool_used || null,
    tool_output: session.conversationMetadata?.tool_output || null
  };
};

/**
 * GET /sessions
 * Returns all active sessions. Returns an empty array if none exist.
 */
export const getAllSessions = async (req, res, next) => {
  try {
    const sessions = await engine.sessionManager.listSessions();
    const result = [];

    for (const session of sessions) {
      const messages = await engine.conversationManager.getHistory(session.sessionId);
      result.push(formatSessionJson(session, messages));
    }

    return res.status(200).json(result);
  } catch (error) {
    next(error);
  }
};

/**
 * GET /session
 * Returns the active session. If none exist, automatically creates one.
 */
export const getActiveSession = async (req, res, next) => {
  try {
    let sessions = await engine.sessionManager.listSessions();
    let activeSession;

    if (sessions.length === 0) {
      // Auto-create session if none exist
      activeSession = await engine.sessionManager.createSession(null, 'mock', {});
      await engine.conversationManager.createConversation(activeSession.sessionId);
    } else {
      // Return the most recently updated session
      sessions.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
      activeSession = sessions[0];
    }

    const messages = await engine.conversationManager.getHistory(activeSession.sessionId);
    return res.status(200).json(formatSessionJson(activeSession, messages));
  } catch (error) {
    next(error);
  }
};

/**
 * GET /sessions/:sessionId or GET /session/:id
 * Returns details for a single session.
 */
export const getSessionById = async (req, res, next) => {
  try {
    const sessionId = req.params.sessionId || req.params.id;
    const session = await engine.sessionManager.getSession(sessionId);

    if (!session) {
      return res.status(404).json({
        success: false,
        error: `Session '${sessionId}' not found.`
      });
    }

    const messages = await engine.conversationManager.getHistory(sessionId);
    return res.status(200).json(formatSessionJson(session, messages));
  } catch (error) {
    next(error);
  }
};

/**
 * POST /sessions or POST /session
 * Creates a new session. Accepts provider and metadata optionally in the body.
 */
export const createSession = async (req, res, next) => {
  try {
    const { session_id, sessionId, provider, metadata } = req.body;
    const targetSessionId = sessionId || session_id || null;
    const activeProvider = provider || 'mock';
    const activeMetadata = metadata || {};

    const session = await engine.sessionManager.createSession(
      targetSessionId,
      activeProvider,
      activeMetadata
    );

    // Initialize conversation history array
    await engine.conversationManager.createConversation(session.sessionId);

    return res.status(201).json(formatSessionJson(session, []));
  } catch (error) {
    next(error);
  }
};

/**
 * DELETE /sessions/:sessionId or DELETE /session/:id
 * Deletes a session.
 */
export const deleteSession = async (req, res, next) => {
  try {
    const sessionId = req.params.sessionId || req.params.id;
    const exists = await engine.sessionManager.getSession(sessionId);

    if (!exists) {
      return res.status(404).json({
        success: false,
        error: `Session '${sessionId}' not found.`
      });
    }

    await engine.sessionManager.deleteSession(sessionId);
    await engine.conversationManager.clearHistory(sessionId);

    return res.status(200).json({
      success: true,
      message: `Session '${sessionId}' deleted successfully.`
    });
  } catch (error) {
    next(error);
  }
};
