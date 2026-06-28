/**
 * Class responsible for history trimming, token management, and context limits.
 * This class is completely provider-independent.
 */
export class ContextManager {
  /**
   * Instantiate a ContextManager with default rules.
   * @param {object} [config]
   * @param {number} [config.maxMessageCount] - The fallback maximum message count limit.
   * @param {number} [config.maxTokenLimit] - The fallback token limit.
   * @param {boolean} [config.recentMessagePriority] - Prioritize recent messages when trimming.
   */
  constructor(config = {}) {
    this.defaultMaxMessageCount = config.maxMessageCount || 50;
    this.defaultMaxTokenLimit = config.maxTokenLimit || 4096;
    this.defaultRecentMessagePriority = config.recentMessagePriority !== false;
  }

  /**
   * Approximates the token count of a single message.
   * Leverages a rough character-based heuristic (~4 characters per token).
   * @param {object} message - Message object containing text content
   * @returns {number} Estimated token count
   */
  estimateTokens(message) {
    if (!message || !message.content) return 0;
    return Math.ceil(message.content.length / 4);
  }

  /**
   * Trims message history to fit within defined message counts and token limits.
   * Always attempts to keep the system prompt intact if it is present.
   * @param {Array<object>} messages - The input message array.
   * @param {object} [options] - Overrides for trimming rules.
   * @param {number} [options.maxMessageCount] - Max messages to retain.
   * @param {number} [options.maxTokenLimit] - Max tokens to allow.
   * @returns {Promise<Array<object>>} Trimmed message array.
   */
  async trimHistory(messages, options = {}) {
    const maxMessageCount = options.maxMessageCount || this.defaultMaxMessageCount;
    const maxTokenLimit = options.maxTokenLimit || this.defaultMaxTokenLimit;

    if (!messages || messages.length === 0) {
      return [];
    }

    let trimmed = [...messages];

    // 1. Trim by message count first (keep recent)
    if (trimmed.length > maxMessageCount) {
      const systemPrompt = trimmed[0].role === 'system' ? trimmed[0] : null;
      const startIndex = systemPrompt ? trimmed.length - maxMessageCount + 1 : trimmed.length - maxMessageCount;
      trimmed = trimmed.slice(startIndex);
      
      if (systemPrompt) {
        trimmed.unshift(systemPrompt);
      }
    }

    // 2. Trim by token limit (working from newest to oldest)
    let totalTokens = 0;
    const systemPrompt = trimmed.length > 0 && trimmed[0].role === 'system' ? trimmed[0] : null;
    const systemTokens = systemPrompt ? this.estimateTokens(systemPrompt) : 0;
    
    totalTokens += systemTokens;

    const keptMessages = [];
    const loopStartIndex = systemPrompt ? 1 : 0;
    
    // Process messages starting from the most recent (end of array)
    for (let i = trimmed.length - 1; i >= loopStartIndex; i--) {
      const msg = trimmed[i];
      const tokens = this.estimateTokens(msg);
      
      if (totalTokens + tokens <= maxTokenLimit) {
        keptMessages.unshift(msg);
        totalTokens += tokens;
      } else {
        // Stop adding older messages once the limit is breached
        break;
      }
    }

    if (systemPrompt) {
      keptMessages.unshift(systemPrompt);
    }

    return keptMessages;
  }
}
