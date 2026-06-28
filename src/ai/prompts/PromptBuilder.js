import { SystemPrompt } from './SystemPrompt.js';

/**
 * Builds standard LLM message objects from multiple structural prompt pieces.
 */
export class PromptBuilder {
  /**
   * Create a PromptBuilder.
   * @param {object} [config]
   * @param {string} [config.systemPrompt] - Default custom system prompt, if any.
   */
  constructor(config = {}) {
    this.systemPromptManager = new SystemPrompt(config.systemPrompt);
  }

  /**
   * Assembles a structured chat messages array.
   * @param {object} params
   * @param {Array<object>} params.history - The trimmed conversation history message array.
   * @param {string} params.userMessage - The new incoming user query.
   * @param {string} [params.relevantContext] - Relevant context (e.g. system state or retrieval results).
   * @returns {Array<object>} Chat LLM compatible message payload array.
   */
  build({ history = [], userMessage, relevantContext = null }) {
    if (!userMessage || typeof userMessage !== 'string' || !userMessage.trim()) {
      throw new Error("Current user message is required to build prompt payload.");
    }

    const messages = [];

    // 1. Add System Prompt instructions first
    messages.push({
      role: 'system',
      content: this.systemPromptManager.getPrompt()
    });

    // 2. Add Context block if provided
    if (relevantContext && typeof relevantContext === 'string' && relevantContext.trim()) {
      messages.push({
        role: 'system',
        content: `[Context/Retrieval Information]\n${relevantContext.trim()}`
      });
    }

    // 3. Add historical messages (avoid duplicate system prompt from history)
    for (const msg of history) {
      if (msg.role !== 'system') {
        messages.push({
          role: msg.role,
          content: msg.content
        });
      }
    }

    // 4. Add the latest user message
    messages.push({
      role: 'user',
      content: userMessage.trim()
    });

    return messages;
  }
}
