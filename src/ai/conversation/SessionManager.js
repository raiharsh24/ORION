import { randomUUID } from 'crypto';

/**
 * Represents an individual chat session.
 */
export class ChatSession {
  /**
   * Create a new ChatSession.
   * @param {string} [sessionId] - Optional unique identifier, defaults to a random UUID.
   * @param {string} [provider] - The active AI provider for this session.
   * @param {object} [metadata] - Additional contextual metadata for this session.
   */
  constructor(sessionId = null, provider = 'mock', metadata = {}) {
    this.sessionId = sessionId || randomUUID();
    this.createdAt = new Date().toISOString();
    this.updatedAt = new Date().toISOString();
    this.conversationState = 'active'; // 'active' | 'archived' | 'paused'
    this.activeProvider = provider;
    this.conversationMetadata = metadata;
  }

  /**
   * Update fields of the session.
   * @param {object} updates - Key-value map of updates to apply.
   */
  update(updates = {}) {
    const protectedFields = ['sessionId', 'createdAt'];
    for (const [key, value] of Object.entries(updates)) {
      if (!protectedFields.includes(key)) {
        this[key] = value;
      }
    }
    this.updatedAt = new Date().toISOString();
  }
}

/**
 * Manages life-cycle operations for multiple active ChatSessions.
 */
export class SessionManager {
  constructor() {
    /**
     * Cache storage of active chat sessions.
     * @type {Map<string, ChatSession>}
     * @private
     */
    this._sessions = new Map();
  }

  /**
   * Creates and registers a new chat session.
   * @param {string} [sessionId] - Optional session ID.
   * @param {string} [provider] - Active provider name.
   * @param {object} [metadata] - Optional session metadata.
   * @returns {Promise<ChatSession>} The newly created session.
   */
  async createSession(sessionId = null, provider = 'mock', metadata = {}) {
    const session = new ChatSession(sessionId, provider, metadata);
    this._sessions.set(session.sessionId, session);
    return session;
  }

  /**
   * Retrieves an active session by its ID.
   * @param {string} sessionId - The session ID to look up.
   * @returns {Promise<ChatSession|null>} The found session, or null if none.
   */
  async getSession(sessionId) {
    if (!sessionId) return null;
    return this._sessions.get(sessionId) || null;
  }

  /**
   * Updates an existing session's configuration and metadata.
   * @param {string} sessionId - The session ID to update.
   * @param {object} updates - The property updates to apply.
   * @returns {Promise<ChatSession>} The updated session.
   * @throws {Error} if session does not exist.
   */
  async updateSession(sessionId, updates = {}) {
    const session = this._sessions.get(sessionId);
    if (!session) {
      throw new Error(`Session with ID '${sessionId}' not found.`);
    }
    session.update(updates);
    return session;
  }

  /**
   * Deletes a session from the manager.
   * @param {string} sessionId - The session ID to remove.
   * @returns {Promise<boolean>} True if session was deleted, false if it didn't exist.
   */
  async deleteSession(sessionId) {
    return this._sessions.delete(sessionId);
  }

  /**
   * Lists all registered chat sessions.
   * @returns {Promise<Array<ChatSession>>} Array of all active sessions.
   */
  async listSessions() {
    return Array.from(this._sessions.values());
  }

  /**
   * Clear all sessions.
   * @returns {Promise<void>}
   */
  async clear() {
    this._sessions.clear();
  }
}
