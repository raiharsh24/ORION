/**
 * @abstract
 * BaseProvider serves as the abstract interface for all LLM providers in FRIDAY.
 * Subclasses must override abstract methods or throw errors.
 */
export class BaseProvider {
  /**
   * Base provider constructor.
   * @param {object} [config] - Provider-specific configuration.
   */
  constructor(config = {}) {
    if (new.target === BaseProvider) {
      throw new TypeError("Cannot construct BaseProvider instances directly. Derive a subclass instead.");
    }
    this.config = config;
    this.name = config.name || "GenericProvider";
  }

  /**
   * Initializes the client/connection (e.g. validate API keys, load local models).
   * @abstract
   * @returns {Promise<void>}
   */
  async initialize() {
    throw new Error(`Method 'initialize()' must be implemented by subclass ${this.constructor.name}`);
  }

  /**
   * Executes a standard chat prompt completion call.
   * @abstract
   * @param {Array<object>} messages - Standard messages payload array.
   * @param {object} [options] - Additional runtime options (temperature, topP, etc.).
   * @returns {Promise<object>} Standard raw completion details (containing text, model, token usage, etc.).
   */
  async chat(messages, options = {}) {
    throw new Error(`Method 'chat(messages, options)' must be implemented by subclass ${this.constructor.name}`);
  }

  /**
   * Executes a streaming chat completion call.
   * @abstract
   * @param {Array<object>} messages - Standard messages payload array.
   * @param {object} [options] - Additional runtime options.
   * @returns {Promise<AsyncIterable<string>|any>} An async iterable stream or event emitter source.
   */
  async stream(messages, options = {}) {
    throw new Error(`Method 'stream(messages, options)' must be implemented by subclass ${this.constructor.name}`);
  }

  /**
   * Verifies connection or service state.
   * @abstract
   * @returns {Promise<boolean>} True if provider service is responsive, false otherwise.
   */
  async healthCheck() {
    throw new Error(`Method 'healthCheck()' must be implemented by subclass ${this.constructor.name}`);
  }

  /**
   * Returns current active model name and capacities.
   * @abstract
   * @returns {Promise<object>} Object with name, type, and limits details.
   */
  async getModelInfo() {
    throw new Error(`Method 'getModelInfo()' must be implemented by subclass ${this.constructor.name}`);
  }
}
