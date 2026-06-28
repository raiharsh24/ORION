import { BaseProvider } from './BaseProvider.js';
import { GeminiProvider } from './GeminiProvider.js';

/**
 * A mock provider implementation for sandbox environments and testing.
 * @extends BaseProvider
 */
class StubProvider extends BaseProvider {
  constructor(config = {}) {
    super({ name: "StubProvider", ...config });
    this.modelName = config.modelName || "mock-model";
    this.initialized = false;
  }

  async initialize() {
    this.initialized = true;
  }

  async chat(messages, options = {}) {
    if (!this.initialized) {
      await this.initialize();
    }

    const lastUserMessage = messages
      .slice()
      .reverse()
      .find(m => m.role === 'user');

    const responseContent = lastUserMessage
      ? `Stub response matching query: "${lastUserMessage.content}"`
      : "Stub response: No user query detected.";

    return {
      text: responseContent,
      model: this.modelName,
      usage: {
        promptTokens: messages.length * 5,
        completionTokens: 15,
        totalTokens: messages.length * 5 + 15
      },
      metadata: {
        timestamp: new Date().toISOString(),
        temperature: options.temperature || 0.7
      }
    };
  }

  async *stream(messages, options = {}) {
    if (!this.initialized) {
      await this.initialize();
    }

    const chunks = ["Stub", " stream", " chunked", " response", "."];
    for (const chunk of chunks) {
      yield chunk;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
  }

  async healthCheck() {
    return true;
  }

  async getModelInfo() {
    return {
      name: this.modelName,
      maxContextTokens: 4096,
      type: "mock"
    };
  }
}

/**
 * Factory class for registering and instantiating providers via Dependency Injection.
 */
export class ProviderFactory {
  constructor() {
    /**
     * Map of provider name to class constructor reference.
     * @type {Map<string, typeof BaseProvider>}
     * @private
     */
    this._registry = new Map();
    
    // Register GeminiProvider under 'gemini' and as the default 'mock' provider
    this.registerProvider('gemini', GeminiProvider);
    this.registerProvider('mock', GeminiProvider);
  }

  /**
   * Registers a provider class under a specific key.
   * @param {string} type - Provider name key (e.g. 'gemini', 'openai').
   * @param {typeof BaseProvider} ProviderClass - Class extending BaseProvider.
   */
  registerProvider(type, ProviderClass) {
    if (!type || typeof type !== 'string') {
      throw new Error("Provider registration type must be a valid non-empty string.");
    }
    
    if (!(ProviderClass.prototype instanceof BaseProvider) && ProviderClass !== BaseProvider) {
      throw new Error(`Provider class for '${type}' must extend BaseProvider.`);
    }

    this._registry.set(type.toLowerCase(), ProviderClass);
  }

  /**
   * Instantiates the requested provider with configuration options.
   * @param {string} type - The provider name key.
   * @param {object} [config] - Constructor options for the provider.
   * @returns {BaseProvider} The instantiated provider class.
   */
  createProvider(type, config = {}) {
    if (!type || typeof type !== 'string') {
      throw new Error("Provider type must be specified.");
    }

    const ProviderClass = this._registry.get(type.toLowerCase());
    if (!ProviderClass) {
      throw new Error(
        `AI Provider '${type}' is not registered. Available: ${Array.from(this._registry.keys()).join(', ')}`
      );
    }

    return new ProviderClass(config);
  }

  /**
   * Check if a provider is registered.
   * @param {string} type - Provider type name.
   * @returns {boolean}
   */
  hasProvider(type) {
    return this._registry.has(type.toLowerCase());
  }

  /**
   * Lists registered provider types.
   * @returns {Array<string>} List of keys.
   */
  listProviders() {
    return Array.from(this._registry.keys());
  }
}
