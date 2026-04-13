/**
 * ChatGPT Platform Module
 * Extracts conversations from chat.openai.com
 */

const ChatGPTPlatform = {
  id: 'chatgpt',
  name: 'ChatGPT',

  /**
   * Extract conversation ID from URL or page
   */
  extractConversationId() {
    // ChatGPT URLs are like: https://chat.openai.com/c/abc-123-def
    const match = window.location.pathname.match(/\/c\/([a-f0-9-]+)/);
    if (match) {
      return match[1];
    }
    
    // Fallback: generate from timestamp if new conversation
    return `chatgpt-${Date.now()}`;
  },

  /**
   * Extract all messages from the page
   */
  extractMessages() {
    const messages = [];
    
    // ChatGPT message containers (as of March 2026)
    // This selector targets conversation turn containers
    const messageElements = document.querySelectorAll('[data-message-author-role]');
    
    messageElements.forEach((element, index) => {
      const message = this.extractMessageFromElement(element, index);
      if (message) {
        messages.push(message);
      }
    });

    return messages;
  },

  /**
   * Extract messages from a specific node (for MutationObserver)
   */
  extractMessagesFromNode(node) {
    const messages = [];
    
    // Check if node itself is a message
    if (node.hasAttribute && node.hasAttribute('data-message-author-role')) {
      const message = this.extractMessageFromElement(node, 0);
      if (message) {
        messages.push(message);
      }
    }
    
    // Check children
    const messageElements = node.querySelectorAll('[data-message-author-role]');
    messageElements.forEach((element, index) => {
      const message = this.extractMessageFromElement(element, index);
      if (message) {
        messages.push(message);
      }
    });

    return messages;
  },

  /**
   * Extract message data from a DOM element
   */
  extractMessageFromElement(element, index) {
    try {
      // Get role (user or assistant)
      const role = element.getAttribute('data-message-author-role');
      if (!role) return null;

      // Get message ID if available
      const messageId = element.getAttribute('data-message-id') || `msg-${index}`;

      // Extract text content
      // ChatGPT renders markdown, so we want the processed text
      const contentElement = element.querySelector('[data-message-author-role] > div > div');
      if (!contentElement) return null;

      const text = contentElement.innerText.trim();
      if (!text) return null;

      // Extract timestamp if available (may not always be present)
      const timestamp = new Date().toISOString();

      return {
        id: messageId,
        role: role, // 'user' or 'assistant'
        text: text,
        timestamp: timestamp,
        platform: this.id,
        metadata: {
          index: index,
          hasCodeBlocks: contentElement.querySelectorAll('code').length > 0,
          hasImages: contentElement.querySelectorAll('img').length > 0
        }
      };
    } catch (error) {
      console.error('[0Latency] Error extracting message:', error);
      return null;
    }
  }
};

// Initialize observer when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const observer = new window.MessageObserver(ChatGPTPlatform);
    observer.init();
  });
} else {
  const observer = new window.MessageObserver(ChatGPTPlatform);
  observer.init();
}
