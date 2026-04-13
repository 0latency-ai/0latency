/**
 * Base Message Observer
 * Monitors DOM for new messages and extracts conversation data
 */

class MessageObserver {
  constructor(platform) {
    this.platform = platform;
    this.observer = null;
    this.messageQueue = [];
    this.conversationId = null;
    this.isEnabled = false;
  }

  /**
   * Initialize the observer
   */
  async init() {
    console.log(`[0Latency] Initializing observer for ${this.platform.name}`);
    
    // Check if extension is enabled for this platform
    const settings = await this.getSettings();
    if (!settings.autoSync || !settings.platforms[this.platform.id]) {
      console.log(`[0Latency] ${this.platform.name} sync disabled in settings`);
      return;
    }

    this.isEnabled = true;

    // Extract existing conversation ID
    this.conversationId = this.platform.extractConversationId();
    console.log(`[0Latency] Conversation ID: ${this.conversationId}`);

    // Process existing messages on page load
    this.processExistingMessages();

    // Set up MutationObserver for new messages
    this.setupObserver();

    console.log(`[0Latency] Observer initialized for ${this.platform.name}`);
  }

  /**
   * Set up MutationObserver
   */
  setupObserver() {
    const targetNode = document.body;
    const config = {
      childList: true,
      subtree: true,
      characterData: true
    };

    this.observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              this.checkForNewMessages(node);
            }
          });
        }
      }
    });

    this.observer.observe(targetNode, config);
  }

  /**
   * Process messages that already exist on the page
   */
  processExistingMessages() {
    const messages = this.platform.extractMessages();
    console.log(`[0Latency] Found ${messages.length} existing messages`);
    
    if (messages.length > 0) {
      this.queueMessages(messages);
    }
  }

  /**
   * Check if a newly added node contains messages
   */
  checkForNewMessages(node) {
    const messages = this.platform.extractMessagesFromNode(node);
    if (messages.length > 0) {
      console.log(`[0Latency] Found ${messages.length} new messages`);
      this.queueMessages(messages);
    }
  }

  /**
   * Add messages to queue and process
   */
  queueMessages(messages) {
    this.messageQueue.push(...messages);
    this.processQueue();
  }

  /**
   * Process queued messages
   */
  async processQueue() {
    if (this.messageQueue.length === 0) return;

    const settings = await this.getSettings();
    
    if (settings.syncFrequency === 'realtime') {
      // Send immediately
      await this.sendToBackground(this.messageQueue);
      this.messageQueue = [];
    } else {
      // Batch mode: send when we hit batch size
      if (this.messageQueue.length >= settings.batchSize) {
        await this.sendToBackground(this.messageQueue);
        this.messageQueue = [];
      }
    }
  }

  /**
   * Send messages to background script for API upload
   */
  async sendToBackground(messages) {
    try {
      const response = await chrome.runtime.sendMessage({
        action: 'storeMemories',
        payload: {
          platform: this.platform.id,
          conversationId: this.conversationId,
          messages: messages
        }
      });

      if (response.success) {
        console.log(`[0Latency] Successfully stored ${messages.length} messages`);
      } else {
        console.error('[0Latency] Failed to store messages:', response.error);
      }
    } catch (error) {
      console.error('[0Latency] Error sending to background:', error);
    }
  }

  /**
   * Get settings from storage
   */
  async getSettings() {
    const result = await chrome.storage.sync.get(['zl_settings']);
    return result['zl_settings'] || {
      autoSync: true,
      syncFrequency: 'realtime',
      batchSize: 5,
      platforms: {
        chatgpt: true,
        claude: true,
        gemini: true
      }
    };
  }

  /**
   * Stop observing
   */
  disconnect() {
    if (this.observer) {
      this.observer.disconnect();
      console.log(`[0Latency] Observer disconnected for ${this.platform.name}`);
    }
  }
}

// Export for platform modules
window.MessageObserver = MessageObserver;
