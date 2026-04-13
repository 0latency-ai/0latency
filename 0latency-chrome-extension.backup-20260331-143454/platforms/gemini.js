/**
 * Gemini Platform Module
 * Extracts conversations from gemini.google.com
 */

const GeminiPlatform = {
  id: 'gemini',
  name: 'Gemini',

  /**
   * Extract conversation ID from URL or page
   */
  extractConversationId() {
    // Gemini URLs are like: https://gemini.google.com/app/abc123def456
    // or https://gemini.google.com/app
    const match = window.location.pathname.match(/\/app\/([a-f0-9]+)/);
    if (match) {
      return match[1];
    }
    
    // Check for conversation ID in URL hash
    const hashMatch = window.location.hash.match(/conversation\/([a-f0-9-]+)/);
    if (hashMatch) {
      return hashMatch[1];
    }
    
    // Fallback: generate from timestamp if new conversation
    return `gemini-${Date.now()}`;
  },

  /**
   * Extract all messages from the page
   */
  extractMessages() {
    const messages = [];
    
    // Gemini message containers (as of March 2026)
    // Gemini uses Material Design components with specific attributes
    const selectors = [
      'message-content',
      '[data-message-author-role]',
      '.conversation-turn',
      'model-response-text',
      'user-message',
      '[class*="message"]'
    ];
    
    let messageElements = [];
    for (const selector of selectors) {
      messageElements = document.querySelectorAll(selector);
      if (messageElements.length > 0) break;
    }
    
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
    
    // Check if node itself is a message container
    const nodeName = (node.nodeName || '').toLowerCase();
    const className = node.className || '';
    
    if (nodeName === 'message-content' || 
        nodeName === 'model-response-text' ||
        nodeName === 'user-message' ||
        className.includes('message') ||
        className.includes('conversation-turn')) {
      const message = this.extractMessageFromElement(node, 0);
      if (message) {
        messages.push(message);
      }
    }
    
    // Check children with multiple selector strategies
    const selectors = [
      'message-content',
      '[data-message-author-role]',
      '.conversation-turn',
      'model-response-text',
      'user-message',
      '[class*="message"]'
    ];
    
    for (const selector of selectors) {
      const messageElements = node.querySelectorAll(selector);
      messageElements.forEach((element, index) => {
        const message = this.extractMessageFromElement(element, index);
        if (message) {
          messages.push(message);
        }
      });
      if (messages.length > 0) break;
    }

    return messages;
  },

  /**
   * Extract message data from a DOM element
   */
  extractMessageFromElement(element, index) {
    try {
      // Determine role based on element tag name, attributes, or class
      let role = 'assistant'; // default to assistant
      const nodeName = (element.nodeName || '').toLowerCase();
      const className = element.className || '';
      
      // Check data attribute first
      if (element.hasAttribute('data-message-author-role')) {
        role = element.getAttribute('data-message-author-role');
      } else if (nodeName === 'user-message' || className.includes('user')) {
        role = 'user';
      } else if (nodeName === 'model-response-text' || className.includes('model') || className.includes('assistant')) {
        role = 'assistant';
      }
      
      // Try to detect role from nested elements
      const userMarker = element.querySelector('user-message, [class*="user"]');
      const modelMarker = element.querySelector('model-response-text, [class*="model"], [class*="assistant"]');
      if (userMarker) role = 'user';
      if (modelMarker) role = 'assistant';

      // Generate message ID
      const messageId = element.getAttribute('data-message-id') || 
                       element.id || 
                       `gemini-msg-${index}-${Date.now()}`;

      // Extract text content
      let text = '';
      const contentSelectors = [
        'message-content',
        'model-response-text',
        '.message-content',
        '.model-response',
        '.response-container',
        '[class*="text"]',
        'p, div'
      ];
      
      for (const selector of contentSelectors) {
        const contentElement = element.querySelector(selector);
        if (contentElement) {
          text = contentElement.innerText.trim();
          if (text) break;
        }
      }
      
      // Fallback to element's own text
      if (!text) {
        text = element.innerText.trim();
      }
      
      if (!text) return null;

      // Extract timestamp
      const timestamp = new Date().toISOString();

      return {
        id: messageId,
        role: role,
        text: text,
        timestamp: timestamp,
        platform: this.id,
        metadata: {
          index: index,
          hasCodeBlocks: element.querySelectorAll('code, pre').length > 0,
          hasImages: element.querySelectorAll('img').length > 0,
          hasChips: element.querySelectorAll('[class*="chip"]').length > 0
        }
      };
    } catch (error) {
      console.error('[0Latency] Error extracting Gemini message:', error);
      return null;
    }
  }
};

// Initialize observer when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const observer = new window.MessageObserver(GeminiPlatform);
    observer.init();
  });
} else {
  const observer = new window.MessageObserver(GeminiPlatform);
  observer.init();
}
