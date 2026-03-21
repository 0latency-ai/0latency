/**
 * Claude.ai Content Script — Observes conversation turns on claude.ai
 */

(function() {
  'use strict';

  const PLATFORM = 'claude';
  let lastProcessedIndex = -1;
  let observer = null;

  function getSessionKey() {
    const match = window.location.pathname.match(/\/chat\/([a-f0-9-]+)/);
    return match ? match[1] : 'unknown';
  }

  function extractTurns() {
    const turns = [];
    
    // Claude uses [data-testid="user-message"] and [data-testid="ai-message"] 
    // or role-based classes
    const humanMessages = document.querySelectorAll(
      '[data-testid="user-message"], .font-user-message, [class*="human-turn"]'
    );
    const assistantMessages = document.querySelectorAll(
      '[data-testid="ai-message"], .font-claude-message, [class*="ai-turn"] .markdown'
    );
    
    // Fallback: iterate through conversation container
    const container = document.querySelector('[class*="conversation"], main');
    if (container) {
      const allMessages = container.querySelectorAll('[class*="message"], [data-testid*="message"]');
      let currentHuman = null;
      
      for (const msg of allMessages) {
        const isHuman = msg.matches('[data-testid="user-message"], [class*="human"], [class*="user"]') ||
                        msg.querySelector('[class*="human"], [class*="user"]');
        const isAssistant = msg.matches('[data-testid="ai-message"], [class*="assistant"], [class*="ai-turn"]') ||
                           msg.querySelector('[class*="assistant"], [class*="claude"]');
        
        const text = msg.innerText?.trim() || '';
        if (!text || text.length < 5) continue;
        
        if (isHuman) {
          currentHuman = text;
        } else if (isAssistant && currentHuman) {
          turns.push({
            humanMessage: currentHuman,
            agentMessage: text,
          });
          currentHuman = null;
        }
      }
    }
    
    return turns;
  }

  function processNewTurns() {
    const turns = extractTurns();
    if (turns.length <= lastProcessedIndex) return;
    
    for (let i = Math.max(0, lastProcessedIndex + 1); i < turns.length; i++) {
      chrome.runtime.sendMessage({
        type: 'EXTRACT_TURN',
        data: {
          humanMessage: turns[i].humanMessage.substring(0, 50000),
          agentMessage: turns[i].agentMessage.substring(0, 50000),
          platform: PLATFORM,
          sessionKey: getSessionKey(),
        },
      }).catch(() => {});
    }
    
    lastProcessedIndex = turns.length - 1;
  }

  function startObserver() {
    const target = document.querySelector('main') || document.body;
    observer = new MutationObserver(() => {
      clearTimeout(startObserver._debounce);
      startObserver._debounce = setTimeout(processNewTurns, 2500);
    });
    observer.observe(target, { childList: true, subtree: true, characterData: true });
  }

  function init() {
    const check = setInterval(() => {
      const msgs = document.querySelectorAll('[data-testid*="message"], [class*="message"]');
      if (msgs.length > 0 || document.querySelector('main')) {
        clearInterval(check);
        const existing = extractTurns();
        lastProcessedIndex = existing.length - 1;
        startObserver();
        console.log('[0Latency] Claude capture active');
      }
    }, 1000);
    setTimeout(() => clearInterval(check), 30000);
  }

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
