/**
 * 0Latency API Client
 * Handles all communication with the 0Latency API
 */

const API_BASE_URL = 'https://api.0latency.ai';

export class ZeroLatencyClient {
  constructor(apiKey) {
    this.apiKey = apiKey;
  }

  /**
   * Store a memory to 0Latency
   * @param {Object} memory - Memory object
   * @param {string} memory.text - The memory text
   * @param {Object} memory.metadata - Additional metadata
   * @returns {Promise<Object>} API response
   */
  async storeMemory(memory) {
    try {
      const response = await fetch(`${API_BASE_URL}/memories`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
          'User-Agent': 'ZeroLatency-Chrome-Extension/0.1.0'
        },
        body: JSON.stringify({
          text: memory.text,
          metadata: {
            ...memory.metadata,
            source: 'chrome-extension',
            captured_at: new Date().toISOString()
          }
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || `API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[0Latency] Store memory error:', error);
      throw error;
    }
  }

  /**
   * Batch store multiple memories
   * @param {Array<Object>} memories - Array of memory objects
   * @returns {Promise<Object>} API response
   */
  async storeMemories(memories) {
    try {
      const response = await fetch(`${API_BASE_URL}/memories/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
          'User-Agent': 'ZeroLatency-Chrome-Extension/0.1.0'
        },
        body: JSON.stringify({
          memories: memories.map(m => ({
            text: m.text,
            metadata: {
              ...m.metadata,
              source: 'chrome-extension',
              captured_at: new Date().toISOString()
            }
          }))
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.message || `API error: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('[0Latency] Batch store error:', error);
      throw error;
    }
  }

  /**
   * Validate API key
   * @returns {Promise<boolean>} True if valid
   */
  async validateKey() {
    try {
      const response = await fetch(`${API_BASE_URL}/tenant-info`, {
        headers: {
          'X-API-Key': this.apiKey
        }
      });
      return response.ok;
    } catch (error) {
      console.error('[0Latency] Validate key error:', error);
      return false;
    }
  }
}
