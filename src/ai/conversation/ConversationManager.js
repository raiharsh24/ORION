/**
 * Represents a single message in a conversation.
 * @typedef {object} Message
 * @property {string} role - 'system' | 'user' | 'assistant'
 * @property {string} content - Text content of the message
 * @property {object} metadata - Optional metadata (tokens, tags, timestamp etc)
 * @property {string} timestamp - ISO string of message creation time
 */

/**
 * Manages conversation history records linked to sessions.
 */
export class ConversationManager {
  constructor() {
    /**
     * Internal storage mapping session IDs to message arrays.
     * @type {Map<string, Array<Message>>}
     * @private
     */
    this._histories = new Map();
  }

  /**
   * Initializes or fetches an existing conversation history array.
   * @param {string} sessionId - The session ID.
   * @returns {Promise<Array<Message>>} The session's history array.
   */
  async createConversation(sessionId) {
    if (!sessionId) {
      throw new Error("Session ID is required to create a conversation.");
    }
    if (!this._histories.has(sessionId)) {
      this._histories.set(sessionId, []);
    }
    return this._histories.get(sessionId);
  }

  /**
   * Appends a message to the session's conversation history.
   * @param {string} sessionId - The target session ID.
   * @param {string} role - The message sender role ('system', 'user', 'assistant').
   * @param {string} content - Message text content.
   * @param {object} [metadata] - Optional message metadata.
   * @returns {Promise<Message>} The generated message object.
   */
  async addMessage(sessionId, role, content, metadata = {}) {
    if (!role || !content) {
      throw new Error("Message role and content are required.");
    }
    
    await this.createConversation(sessionId);
    
    const message = {
      role,
      content,
      metadata,
      timestamp: new Date().toISOString()
    };
    
    this._histories.get(sessionId).push(message);
    return message;
  }

  /**
   * Retrieves the message history list for a session.
   * @param {string} sessionId - The session ID.
   * @returns {Promise<Array<Message>>} The message array.
   */
  async getHistory(sessionId) {
    if (!sessionId) return [];
    return this._histories.get(sessionId) || [];
  }

  /**
   * Clears the conversation history for a session.
   * @param {string} sessionId - The session ID.
   * @returns {Promise<boolean>} True if the history was cleared, false if no session history existed.
   */
  async clearHistory(sessionId) {
    if (this._histories.has(sessionId)) {
      this._histories.set(sessionId, []);
      return true;
    }
    return false;
  }

  /**
   * Generates a summary for long conversation histories (placeholder implementation).
   * @param {string} sessionId - The session ID.
   * @returns {Promise<string>} A summarized description of the conversation.
   */
  async summarize(sessionId) {
    const history = await this.getHistory(sessionId);
    if (history.length === 0) {
      return "Conversation is empty.";
    }
    
    // Placeholder implementation for future development
    // In future versions, this would invoke a summarization LLM
    const totalChars = history.reduce((sum, msg) => sum + msg.content.length, 0);
    return `[Placeholder Summary: Conversation contains ${history.length} messages with approx ${totalChars} characters]`;
  }
}
