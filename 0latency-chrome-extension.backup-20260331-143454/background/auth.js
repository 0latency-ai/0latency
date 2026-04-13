/**
 * Authentication & API Key Management
 */

export class AuthManager {
  static STORAGE_KEY = 'zl_api_key';
  static SETTINGS_KEY = 'zl_settings';

  /**
   * Get stored API key
   * @returns {Promise<string|null>}
   */
  static async getApiKey() {
    const result = await chrome.storage.local.get([this.STORAGE_KEY]);
    return result[this.STORAGE_KEY] || null;
  }

  /**
   * Store API key
   * @param {string} apiKey 
   * @returns {Promise<void>}
   */
  static async setApiKey(apiKey) {
    await chrome.storage.local.set({ [this.STORAGE_KEY]: apiKey });
  }

  /**
   * Clear stored API key
   * @returns {Promise<void>}
   */
  static async clearApiKey() {
    await chrome.storage.local.remove([this.STORAGE_KEY]);
  }

  /**
   * Get extension settings
   * @returns {Promise<Object>}
   */
  static async getSettings() {
    const result = await chrome.storage.local.get([this.SETTINGS_KEY]);
    return result[this.SETTINGS_KEY] || {
      autoSync: true,
      syncFrequency: 'realtime', // 'realtime' | 'batch'
      batchSize: 5,
      platforms: {
        chatgpt: true,
        claude: true,
        gemini: true
      }
    };
  }

  /**
   * Update settings
   * @param {Object} settings 
   * @returns {Promise<void>}
   */
  static async updateSettings(settings) {
    const current = await this.getSettings();
    await chrome.storage.local.set({
      [this.SETTINGS_KEY]: { ...current, ...settings }
    });
  }

  /**
   * Check if user is authenticated
   * @returns {Promise<boolean>}
   */
  static async isAuthenticated() {
    const apiKey = await this.getApiKey();
    return apiKey !== null && apiKey.length > 0;
  }
}
