/**
 * Claude Platform Module
 * Extracts conversations from claude.ai
 */

const ClaudePlatform = {
  id: 'claude',
  name: 'Claude',

  /**
   * Extract conversation ID from URL or page
   */
  extractConversationId() {
    // Claude URLs are like: https://claude.ai/chat/abc-123-def-456
    const match = window.location.pathname.match(/\/chat\/([a-f0-9-]+)/);
    if (match) {
      return match[1];
    }
    
    // Fallback: generate from timestamp if new conversation
    return `claude-${Date.now()}`;
  },

  /**
   * Extract all messages from the page
   */
  extractMessages() {
    const messages = [];
    
    // Claude message containers (as of March 2026)
    // Claude uses div elements with specific classes for message turns
    // Try multiple selectors as Claude UI may vary
    const selectors = [
      '[class*="MessageGroup"]',
      '[class*="message"]',
      'div[data-is-streaming]',
      '.font-user-message, .font-claude-message'
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
    if (node.className && (
      node.className.includes('MessageGroup') || 
      node.className.includes('message') ||
      node.className.includes('font-user-message') ||
      node.className.includes('font-claude-message')
    )) {
      const message = this.extractMessageFromElement(node, 0);
      if (message) {
        messages.push(message);
      }
    }
    
    // Check children with multiple selector strategies
    const selectors = [
      '[class*="MessageGroup"]',
      '[class*="message"]',
      'div[data-is-streaming]',
      '.font-user-message, .font-claude-message'
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
      // Determine role based on class names or structure
      let role = 'assistant'; // default to assistant
      const className = element.className || '';
      
      if (className.includes('user') || className.includes('Human')) {
        role = 'user';
      } else if (className.includes('claude') || className.includes('Assistant')) {
        role = 'assistant';
      }
      
      // Try to detect role from nested elements
      const userMarker = element.querySelector('[class*="user"]');
      const assistantMarker = element.querySelector('[class*="claude"], [class*="assistant"]');
      if (userMarker) role = 'user';
      if (assistantMarker) role = 'assistant';

      // Generate message ID
      const messageId = element.id || `claude-msg-${index}-${Date.now()}`;

      // Extract text content
      // Try multiple content selectors
      let text = '';
      const contentSelectors = [
        '.font-user-message',
        '.font-claude-message',
        '[class*="MessageContent"]',
        '[class*="content"]',
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
          hasArtifacts: element.querySelectorAll('[class*="artifact"]').length > 0
        }
      };
    } catch (error) {
      console.error('[0Latency] Error extracting Claude message:', error);
      return null;
    }
  }
};

// Initialize observer when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    const observer = new window.MessageObserver(ClaudePlatform);
    observer.init();
  });
} else {
  const observer = new window.MessageObserver(ClaudePlatform);
  observer.init();
}
