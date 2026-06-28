import { OrionEngine } from '../../../src/ai/OrionEngine.js';

// Shared singleton OrionEngine instance
// Forced reload comment
export const engine = new OrionEngine({
  context: { maxMessageCount: 50, maxTokenLimit: 4096 }
});
