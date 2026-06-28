import { BaseProvider } from './BaseProvider.js';
import { GoogleGenAI } from '@google/genai';

const MODEL_TOKEN_LIMITS = {
  'gemini-1.5-flash': 1048576,
  'gemini-1.5-pro': 2097152,
  'gemini-2.0-flash': 1048576,
  'gemini-2.5-flash': 1048576,
  'gemini-2.5-pro': 2097152
};

/**
 * Adapter provider for Google Gemini models.
 * @extends BaseProvider
 */
export class GeminiProvider extends BaseProvider {
  constructor(config = {}) {
    super({ name: "GeminiProvider", ...config });
    this.apiKey = config.apiKey || process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || '';
    this.modelName = config.modelName || process.env.MODEL_NAME || 'gemini-1.5-flash';
    this.ai = null;
    this.initialized = false;
  }

  async initialize() {
    if (!this.apiKey) {
      throw new Error("GEMINI_API_KEY is missing or empty. Please verify settings.");
    }
    // Instantiate GoogleGenAI client with the key
    this.ai = new GoogleGenAI({ apiKey: this.apiKey });
    this.initialized = true;
  }

  /**
   * Helper to format generic message histories into Gemini API contents structure.
   * @param {Array} messages - Message objects with role ('user' | 'assistant') and content.
   * @returns {Array} List of Gemini-compatible contents.
   * @private
   */
  _formatMessages(messages) {
    return messages.map(m => ({
      role: m.role === 'assistant' ? 'model' : 'user',
      parts: [{ text: m.content }]
    }));
  }

  async estimateTokens(messages) {
    if (!this.initialized) {
      await this.initialize();
    }

    try {
      const contents = this._formatMessages(messages);
      const res = await this.ai.models.countTokens({
        model: this.modelName,
        contents: contents
      });
      if (res && typeof res.totalTokens === 'number') {
        return res.totalTokens;
      }
    } catch (e) {
      console.warn("Failed to count tokens using API, falling back to estimation:", e.message);
    }

    // Character-based fallback (~3.5 chars per token)
    const totalChars = messages.reduce((acc, m) => acc + (m.content ? m.content.length : 0), 0);
    return Math.ceil(totalChars / 3.5);
  }

  async chat(messages, options = {}) {
    if (!this.initialized) {
      await this.initialize();
    }

    if (options.signal?.aborted) {
      throw new DOMException("The operation was aborted.", "AbortError");
    }

    try {
      const contents = this._formatMessages(messages);
      if (options.signal?.aborted) {
        throw new DOMException("The operation was aborted.", "AbortError");
      }
      const response = await this.ai.models.generateContent({
        model: this.modelName,
        contents: contents,
        config: {
          temperature: options.temperature ?? 0.7,
          maxOutputTokens: options.maxTokens ?? 2048
        }
      });

      const responseText = response.text || '';
      let promptTokens = response.usageMetadata?.promptTokenCount;
      let completionTokens = response.usageMetadata?.candidatesTokenCount;

      if (promptTokens == null || completionTokens == null) {
        const estTotal = await this.estimateTokens(messages);
        const promptText = messages.map(m => m.content).join(' ');
        const promptRatio = promptText.length / (promptText.length + responseText.length || 1);
        promptTokens = Math.max(1, Math.round(estTotal * promptRatio));
        completionTokens = Math.max(1, estTotal - promptTokens);
      }

      return {
        text: responseText,
        model: this.modelName,
        usage: {
          promptTokens,
          completionTokens,
          totalTokens: promptTokens + completionTokens
        },
        metadata: {
          timestamp: new Date().toISOString(),
          temperature: options.temperature ?? 0.7
        }
      };
    } catch (err) {
      if (err.name === 'AbortError' || (options.signal && options.signal.aborted)) {
        throw err;
      }
      console.error("Gemini API generateContent error:", err.message);
      throw new Error(`Gemini API Error: ${err.message}`);
    }
  }

  async *stream(messages, options = {}) {
    if (!this.initialized) {
      await this.initialize();
    }

    try {
      const contents = this._formatMessages(messages);
      const responseStream = await this.ai.models.generateContentStream({
        model: this.modelName,
        contents: contents,
        config: {
          temperature: options.temperature ?? 0.7,
          maxOutputTokens: options.maxTokens ?? 2048
        }
      });

      let lastUsage = null;

      for await (const chunk of responseStream) {
        if (options.signal?.aborted) {
          throw new DOMException("The operation was aborted.", "AbortError");
        }
        const text = chunk.text || "";
        
        if (chunk.usageMetadata) {
          lastUsage = {
            promptTokens: chunk.usageMetadata.promptTokenCount,
            completionTokens: chunk.usageMetadata.candidatesTokenCount,
            totalTokens: chunk.usageMetadata.totalTokenCount
          };
        }

        yield {
          text: text,
          done: false,
          usage: lastUsage
        };
      }

      // Final done chunk emitting real usage
      yield {
        text: "",
        done: true,
        usage: lastUsage
      };
    } catch (err) {
      if (err.name === 'AbortError' || (options.signal && options.signal.aborted)) {
        throw err;
      }
      console.error("Gemini API generateContentStream error:", err.message);
      throw new Error(`Gemini API Streaming Error: ${err.message}`);
    }
  }

  async healthCheck() {
    try {
      if (!this.apiKey) return false;
      if (!this.initialized) {
        await this.initialize();
      }
      return true;
    } catch {
      return false;
    }
  }

  async getModelInfo() {
    return {
      model: this.modelName,
      contextLimit: MODEL_TOKEN_LIMITS[this.modelName] || 1048576,
      provider: "gemini"
    };
  }
}
export default GeminiProvider;
