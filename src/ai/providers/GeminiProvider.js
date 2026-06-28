import { BaseProvider } from './BaseProvider.js';
import { GoogleGenAI } from '@google/genai';

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

  async chat(messages, options = {}) {
    if (!this.initialized) {
      await this.initialize();
    }

    try {
      const contents = this._formatMessages(messages);
      const response = await this.ai.models.generateContent({
        model: this.modelName,
        contents: contents,
        config: {
          temperature: options.temperature ?? 0.7,
          maxOutputTokens: options.maxTokens ?? 2048
        }
      });

      const responseText = response.text || '';
      const promptText = messages.map(m => m.content).join(' ');
      const promptTokens = Math.max(1, Math.floor(promptText.length / 4));
      const completionTokens = Math.max(1, Math.floor(responseText.length / 4));

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

      for await (const chunk of responseStream) {
        const text = chunk.text;
        if (text) {
          yield text;
        }
      }
    } catch (err) {
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
      name: this.modelName,
      maxContextTokens: 1048576,
      type: "llm"
    };
  }
}
export default GeminiProvider;
