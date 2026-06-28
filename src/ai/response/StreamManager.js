import { ResponseFormatter } from './ResponseFormatter.js';

/**
 * Handles text streams from providers, delivering chunk updates to subscribers.
 * Acts as a placeholder design for SSE (Server-Sent Events) or Websocket streams.
 */
export class StreamManager {
  /**
   * Instantiate a StreamManager.
   * @param {object} [options]
   */
  constructor(options = {}) {
    this.options = options;
  }

  /**
   * Subscribes to provider streams, formatting and routing chunks through callbacks.
   * @param {AsyncIterable<string>|any} rawStream - Async iterable chunk source from active provider.
   * @param {object} hooks - Subscription callback callbacks.
   * @param {Function} hooks.onChunk - Triggers on each standard text chunk: (chunkText, formattedObject) => void.
   * @param {Function} hooks.onComplete - Triggers when the stream finishes successfully: (finalFormattedObject) => void.
   * @param {Function} hooks.onError - Triggers on stream exceptions: (formattedErrorObject) => void.
   * @returns {Promise<void>} Resolves when the stream completes.
   */
  async handleStream(rawStream, { onChunk, onComplete, onError }) {
    if (!rawStream) {
      const errorObj = ResponseFormatter.formatError(new Error("No valid stream source provided."));
      if (onError) onError(errorObj);
      return;
    }

    let fullText = "";
    try {
      // Modern JS supports AsyncIterables for LLM stream payloads.
      // This loops through each chunk as it arrives from the LLM provider.
      for await (const chunk of rawStream) {
        fullText += chunk;
        
        const chunkEnvelope = ResponseFormatter.format({
          success: true,
          response: chunk,
          metadata: { isChunk: true }
        });

        if (onChunk) {
          onChunk(chunk, chunkEnvelope);
        }
      }

      // Stream successfully completed, deliver the fully accumulated response
      const finalEnvelope = ResponseFormatter.format({
        success: true,
        response: fullText,
        metadata: { streamCompleted: true }
      });

      if (onComplete) {
        onComplete(finalEnvelope);
      }
    } catch (err) {
      const errorEnvelope = ResponseFormatter.formatError(err);
      if (onError) {
        onError(errorEnvelope);
      }
    }
  }
}
