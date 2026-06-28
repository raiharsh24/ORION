import { SessionManager } from './conversation/SessionManager.js';
import { ConversationManager } from './conversation/ConversationManager.js';
import { ContextManager } from './conversation/ContextManager.js';
import { PromptBuilder } from './prompts/PromptBuilder.js';
import { ProviderFactory } from './providers/ProviderFactory.js';
import { ResponseFormatter } from './response/ResponseFormatter.js';

/**
 * Orchestrator class linking conversation context, prompt assembling, 
 * provider adapters, and response formatters into a single pipeline.
 */
export class FridayEngine {
  /**
   * Instantiate the FridayEngine.
   * @param {object} [config] - System configuration block.
   * @param {object} [config.context] - Configurations passed to ContextManager.
   * @param {object} [config.prompt] - Configurations passed to PromptBuilder.
   * @param {object} [config.providers] - Map of provider type to config properties.
   */
  constructor(config = {}) {
    this.config = config;
    this.sessionManager = new SessionManager();
    this.conversationManager = new ConversationManager();
    this.contextManager = new ContextManager(config.context);
    this.promptBuilder = new PromptBuilder(config.prompt);
    this.providerFactory = new ProviderFactory();
  }

  /**
   * Allows registering custom model adapters dynamically.
   * @param {string} type - Provider name identifier.
   * @param {Function} ProviderClass - Class extending BaseProvider.
   */
  registerProvider(type, ProviderClass) {
    this.providerFactory.registerProvider(type, ProviderClass);
  }

  /**
   * Orchestrates the complete end-to-end conversation chat flow.
   * @param {string} sessionId - The session identifier.
   * @param {string} userMessage - Text content written by the user.
   * @param {string} [relevantContext] - Any optional runtime context or memory logs.
   * @param {object} [options] - Provider call override options.
   * @returns {Promise<object>} StandardizedResponse payload object.
   */
  async chat(sessionId, userMessage, relevantContext = null, options = {}) {
    if (!sessionId) {
      throw new Error("Session ID is required to process conversation chat.");
    }

    let providerName = 'gemini';
    let modelName = 'gemini-1.5-flash';

    try {
      // 1. Fetch or create session state
      let session = await this.sessionManager.getSession(sessionId);
      if (!session) {
        session = await this.sessionManager.createSession(sessionId, options.provider || 'gemini', options.metadata || {});
      }
      
      providerName = session.activeProvider;

      // 2. Add new user query to history
      await this.conversationManager.addMessage(sessionId, 'user', userMessage);

      // 3. Load total history for context analysis
      const history = await this.conversationManager.getHistory(sessionId);

      // 5. Instantiate target provider
      const providerConfig = (this.config.providers && this.config.providers[providerName]) || {};
      const provider = this.providerFactory.createProvider(providerName, providerConfig);
      
      modelName = (await provider.getModelInfo()).name;

      // 4. Trim the history to ensure compatibility with context limitations
      const trimmedHistory = await this.contextManager.trimHistory(history, provider, {
        maxMessageCount: options.maxMessageCount,
        maxTokenLimit: options.maxTokenLimit
      });

      // 5. Construct chat prompt schema
      const messages = this.promptBuilder.build({
        history: trimmedHistory,
        userMessage,
        relevantContext
      });

      // 7. Invoke prompt completion
      const rawResult = await provider.chat(messages, options);

      // 8. Add LLM generation to history
      await this.conversationManager.addMessage(sessionId, 'assistant', rawResult.text, {
        usage: rawResult.usage,
        metadata: rawResult.metadata
      });

      // 9. Keep timestamps updated
      await this.sessionManager.updateSession(sessionId);

      // 10. Format and output final standardized response payload
      return ResponseFormatter.format({
        success: true,
        provider: provider.name,
        model: rawResult.model || modelName,
        response: rawResult.text,
        usage: rawResult.usage,
        metadata: rawResult.metadata
      });

    } catch (error) {
      // Format failures gracefully into consistent envelopes
      return ResponseFormatter.formatError(error, providerName, modelName);
    }
  }

  /**
   * Orchestrates a streaming chat flow.
   * @param {string} sessionId - The session ID.
   * @param {string} userMessage - Text content written by user.
   * @param {string} [relevantContext] - Relevant context.
   * @param {object} [options] - Additional provider settings.
   * @returns {Promise<AsyncIterable<string>>} Async generator yielding stream chunks.
   */
  async streamChat(sessionId, userMessage, relevantContext = null, options = {}) {
    if (!sessionId) {
      throw new Error("Session ID is required to process conversation stream.");
    }

    let session = await this.sessionManager.getSession(sessionId);
    if (!session) {
      session = await this.sessionManager.createSession(sessionId, options.provider || 'gemini', options.metadata || {});
    }

    const providerName = session.activeProvider;

    // Add user query to history
    await this.conversationManager.addMessage(sessionId, 'user', userMessage);

    const providerConfig = (this.config.providers && this.config.providers[providerName]) || {};
    const provider = this.providerFactory.createProvider(providerName, providerConfig);

    // Get current history and trim
    const history = await this.conversationManager.getHistory(sessionId);
    const trimmedHistory = await this.contextManager.trimHistory(history, provider, {
      maxMessageCount: options.maxMessageCount,
      maxTokenLimit: options.maxTokenLimit
    });

    // Build prompt payload
    const messages = this.promptBuilder.build({
      history: trimmedHistory,
      userMessage,
      relevantContext
    });

    // Return the stream source generator
    return provider.stream(messages, options);
  }
}
export default FridayEngine;
