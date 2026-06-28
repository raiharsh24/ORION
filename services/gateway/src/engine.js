import { FridayEngine } from '../../../src/ai/FridayEngine.js';

// Shared singleton FridayEngine instance
// Forced reload comment
export const engine = new FridayEngine({
  context: { maxMessageCount: 50, maxTokenLimit: 4096 }
});
