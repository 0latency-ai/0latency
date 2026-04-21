/**
 * ChatGPT Content Script — Observes conversation turns and sends to background.
 * Works on chatgpt.com and chat.openai.com
 */

(function() {
  'use strict';

  const PLATFORM = 'chatgpt';
  let lastProcessedIndex = -1;
  let observer = null;

  function getSessionKey() {
    // Extract conversation ID from URL
    const match = window.location.pathname.match(/\/c\/([a-f0-9-]+)/);
    return match ? match[1] : 'unknown';
  }

  function extractTurns() {
    const turns = [];
    
    // ChatGPT uses [data-message-author-role] attributes
    const messages = document.querySelectorAll('[data-message-author-role]');
    
    let currentHuman = null;
    
    for (const msg of messages) {
      const role = msg.getAttribute('data-message-author-role');
      const textEl = msg.querySelector('.markdown, .whitespace-pre-wrap, [data-message-id] .text-base');
      const text = textEl?.innerText?.trim() || '';
      
      if (!text) continue;
      
      if (role === 'user') {
        currentHuman = text;
      } else if (role === 'assistant' && currentHuman) {
        turns.push({
          humanMessage: currentHuman,
          agentMessage: text,
        });
        currentHuman = null;
      }
    }
    
    return turns;
  }

  function processNewTurns() {
    const turns = extractTurns();
    
    if (turns.length <= lastProcessedIndex) return;
    
    // Process only new turns
    for (let i = Math.max(0, lastProcessedIndex + 1); i < turns.length; i++) {
      const turn = turns[i];
      
      chrome.runtime.sendMessage({
        type: 'EXTRACT_TURN',
        data: {
          humanMessage: turn.humanMessage.substring(0, 50000),
          agentMessage: turn.agentMessage.substring(0, 50000),
          platform: PLATFORM,
          sessionKey: getSessionKey(),
        },
      }).catch(() => {}); // Extension might be reloading
    }
    
    lastProcessedIndex = turns.length - 1;
  }

  function startObserver() {
    // Watch for new messages being added to the conversation
    const targetNode = document.querySelector('main') || document.body;
    
    observer = new MutationObserver((mutations) => {
      // Debounce — wait for streaming to finish
      clearTimeout(startObserver._debounce);
      startObserver._debounce = setTimeout(() => {
        processNewTurns();
      }, 2000); // Wait 2s after last DOM change (streaming)
    });
    
    observer.observe(targetNode, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  // Initialize after page loads
  function init() {
    // Wait for conversation to load
    const checkReady = setInterval(() => {
      const messages = document.querySelectorAll('[data-message-author-role]');
      if (messages.length > 0 || document.querySelector('main')) {
        clearInterval(checkReady);
        
        // Process existing turns (if re-opening a conversation)
        const existingTurns = extractTurns();
        lastProcessedIndex = existingTurns.length - 1;
        
        startObserver();
        console.log('[0Latency] ChatGPT capture active');
      }
    }, 1000);
    
    // Timeout after 30s
    setTimeout(() => clearInterval(checkReady), 30000);
  }

  // Handle SPA navigation (ChatGPT is a single-page app)
  let currentUrl = location.href;
  new MutationObserver(() => {
    if (location.href !== currentUrl) {
      currentUrl = location.href;
      lastProcessedIndex = -1;
      if (observer) observer.disconnect();
      init();
    }
  }).observe(document, { subtree: true, childList: true });

  init();
})();
