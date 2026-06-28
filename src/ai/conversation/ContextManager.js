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
   * @param {object} provider - LLM Provider adapter instance.
   * @param {object} [options] - Overrides for trimming rules.
   * @param {number} [options.maxMessageCount] - Max messages to retain.
   * @param {number} [options.maxTokenLimit] - Max tokens to allow.
   * @returns {Promise<Array<object>>} Trimmed message array.
   */
  async trimHistory(messages, provider, options = {}) {
    if (!messages || messages.length === 0) {
      return [];
    }

    this.provider = provider;
    const modelInfo = await this.provider.getModelInfo();
    const contextLimit = modelInfo.contextLimit || 1048576;
    const tokenBudget = Math.floor(contextLimit * 0.8);

    let trimmed = [...messages];
    
    // Always preserve system message at index 0 if it is present
    const hasSystem = trimmed[0] && trimmed[0].role === 'system';
    const systemPrompt = hasSystem ? trimmed[0] : null;

    // Helper to evaluate current token usage
    const getBudgetTokens = async (msgs) => {
      return await this.provider.estimateTokens(msgs);
    };

    // Trim oldest messages in pairs (user + assistant) until within budget
    while (trimmed.length > (hasSystem ? 2 : 1)) {
      const currentTokens = await getBudgetTokens(trimmed);
      if (currentTokens <= tokenBudget) {
        break;
      }
      
      // Remove pair from the beginning (index 1 & 2 if system exists, otherwise index 0 & 1)
      if (hasSystem) {
        trimmed.splice(1, 2);
      } else {
        trimmed.splice(0, 2);
      }
    }

    // Ensure system prompt is preserved at index 0
    if (systemPrompt && (trimmed.length === 0 || trimmed[0] !== systemPrompt)) {
      trimmed = trimmed.filter(m => m !== systemPrompt);
      trimmed.unshift(systemPrompt);
    }

    return trimmed;
  }
}
