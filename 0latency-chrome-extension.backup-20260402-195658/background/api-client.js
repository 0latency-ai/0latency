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
   * Get agent_id from settings
   */
  async getAgentId() {
    const result = await chrome.storage.sync.get(['zl_settings']);
    const settings = result.zl_settings || {};
    return settings.agent_id || 'justin';
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
      const agent_id = await this.getAgentId();
      
      const response = await fetch(`${API_BASE_URL}/memories/extract`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
          'User-Agent': 'ZeroLatency-Chrome-Extension/0.1.0'
        },
        body: JSON.stringify({
          agent_id: agent_id,
          content: memory.text,
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
      const agent_id = await this.getAgentId();
      
      // Convert to extract/batch format
      const turns = memories.map(m => ({
        agent_id: agent_id,
        human_message: m.metadata.role === 'user' ? m.text : '',
        agent_message: m.metadata.role === 'assistant' ? m.text : '',
        session_key: m.metadata.conversation_id,
        turn_id: m.metadata.message_id
      })).filter(t => t.human_message || t.agent_message);

      const response = await fetch(`${API_BASE_URL}/extract/batch`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': this.apiKey,
          'User-Agent': 'ZeroLatency-Chrome-Extension/0.1.0'
        },
        body: JSON.stringify({
          turns: turns
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
