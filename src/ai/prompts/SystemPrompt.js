/**
 * Class representing and managing ORION's system instruction/prompt.
 */
export class SystemPrompt {
  /**
   * Create a SystemPrompt manager.
   * @param {string} [customPrompt] - Optional override of default prompt instructions.
   */
  constructor(customPrompt = null) {
    this._customPrompt = customPrompt;
    this._defaultPrompt = [
      "You are ORION, a modular, local-first professional AI assistant inspired by JARVIS/FRIDAY.",
      "Aesthetic Guidelines:",
      "- Be highly professional, technical, helpful, and accurate.",
      "- Be honest: if you do not know something, state it clearly without making assumptions or inventing facts.",
      "- Be concise, unless the user explicitly requests details or comprehensive explanations."
    ].join("\n");
  }

  /**
   * Fetches the current system prompt content.
   * @returns {string} The active system prompt string.
   */
  getPrompt() {
    return this._customPrompt || this._defaultPrompt;
  }

  /**
   * Replaces the active system instructions.
   * @param {string} newPrompt - The custom system prompt to set.
   */
  setPrompt(newPrompt) {
    if (typeof newPrompt !== 'string') {
      throw new Error("System prompt must be a string.");
    }
    this._customPrompt = newPrompt;
  }

  /**
   * Resets the system instructions back to the default ORION prompt.
   */
  reset() {
    this._customPrompt = null;
  }
}
