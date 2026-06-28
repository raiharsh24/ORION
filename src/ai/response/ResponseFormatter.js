/**
 * @typedef {object} StandardizedResponse
 * @property {boolean} success - Represents whether the query was executed successfully.
 * @property {string} provider - The AI provider name (e.g. Gemini, OpenAI).
 * @property {string} model - The specific model name used.
 * @property {string} response - The generated textual response.
 * @property {object} usage - Token usage metadata.
 * @property {number} usage.promptTokens - Count of tokens in prompt context.
 * @property {number} usage.completionTokens - Count of tokens generated.
 * @property {number} usage.totalTokens - Combined token count.
 * @property {object} metadata - Extra runtime or telemetry parameters.
 * @property {string} timestamp - ISO timestamp of formatting operation.
 */

/**
 * Utility class to map provider results into standardized envelopes.
 */
export class ResponseFormatter {
  /**
   * Transforms raw provider payloads into standardized API envelopes.
   * @param {object} params
   * @param {boolean} [params.success=true] - Whether request was successful.
   * @param {string} params.provider - Name of active provider.
   * @param {string} params.model - Name of model.
   * @param {string} params.response - Generated text response.
   * @param {object} [params.usage] - Prompt/Completion usage statistics.
   * @param {number} [params.usage.promptTokens=0]
   * @param {number} [params.usage.completionTokens=0]
   * @param {number} [params.usage.totalTokens=0]
   * @param {object} [params.metadata={}] - Raw metadata properties.
   * @returns {StandardizedResponse} Standard response object.
   */
  static format({
    success = true,
    provider = '',
    model = '',
    response = '',
    usage = {},
    metadata = {}
  }) {
    return {
      success,
      provider,
      model,
      response,
      usage: {
        promptTokens: usage.promptTokens ?? 0,
        completionTokens: usage.completionTokens ?? 0,
        totalTokens: usage.totalTokens ?? 0
      },
      metadata,
      timestamp: new Date().toISOString()
    };
  }

  /**
   * Transforms caught runtime exceptions into standard error envelopes.
   * @param {Error|string} error - The thrown exception.
   * @param {string} [provider=''] - Target provider.
   * @param {string} [model=''] - Target model.
   * @returns {StandardizedResponse} Error formatted response object.
   */
  static formatError(error, provider = '', model = '') {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      provider,
      model,
      response: '',
      usage: {
        promptTokens: 0,
        completionTokens: 0,
        totalTokens: 0
      },
      metadata: {
        error: message
      },
      timestamp: new Date().toISOString()
    };
  }
}
