/**
 * Gemini Content Script — Observes conversation on gemini.google.com
 */

(function() {
  'use strict';

  const PLATFORM = 'gemini';
  let lastProcessedIndex = -1;
  let observer = null;

  function getSessionKey() {
    const match = window.location.pathname.match(/\/app\/([a-f0-9]+)/);
    return match ? match[1] : 'unknown';
  }

  function extractTurns() {
    const turns = [];
    
    // Gemini uses turn containers with user-query and model-response
    const queryChips = document.querySelectorAll(
      'user-query, [class*="query-content"], [class*="user-message"], message-content[data-is-user]'
    );
    const responseChips = document.querySelectorAll(
      'model-response, [class*="response-content"], [class*="model-response"], message-content:not([data-is-user])'
    );
    
    // Fallback: paired iteration through conversation
    const container = document.querySelector('[class*="conversation"], main, [role="main"]');
    if (container) {
      const allTurns = container.querySelectorAll('[class*="turn"], [class*="message-row"]');
      let currentHuman = null;
      
      for (const turn of allTurns) {
        const text = turn.innerText?.trim() || '';
        if (!text || text.length < 5) continue;
        
        const isUser = turn.matches('[class*="user"], [class*="query"]') ||
                      turn.querySelector('[class*="user"], [class*="query"]');
        
        if (isUser) {
          currentHuman = text;
        } else if (currentHuman) {
          turns.push({ humanMessage: currentHuman, agentMessage: text });
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
    const target = document.querySelector('main, [role="main"]') || document.body;
    observer = new MutationObserver(() => {
      clearTimeout(startObserver._debounce);
      startObserver._debounce = setTimeout(processNewTurns, 2500);
    });
    observer.observe(target, { childList: true, subtree: true, characterData: true });
  }

  function init() {
    const check = setInterval(() => {
      if (document.querySelector('main, [role="main"]')) {
        clearInterval(check);
        const existing = extractTurns();
        lastProcessedIndex = existing.length - 1;
        startObserver();
        console.log('[0Latency] Gemini capture active');
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
