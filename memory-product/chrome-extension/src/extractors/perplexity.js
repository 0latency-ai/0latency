/**
 * Perplexity Content Script — Observes conversation on perplexity.ai
 */

(function() {
  'use strict';

  const PLATFORM = 'perplexity';
  let lastProcessedIndex = -1;
  let observer = null;

  function getSessionKey() {
    const match = window.location.pathname.match(/\/search\/([a-zA-Z0-9-]+)/);
    return match ? match[1] : 'unknown';
  }

  function extractTurns() {
    const turns = [];
    
    // Perplexity shows query + answer pairs
    const queries = document.querySelectorAll(
      '[class*="query"], [class*="question"], [class*="user-input"]'
    );
    const answers = document.querySelectorAll(
      '[class*="answer"], [class*="response"], [class*="prose"]'
    );
    
    // Pair them up
    const minLen = Math.min(queries.length, answers.length);
    for (let i = 0; i < minLen; i++) {
      const q = queries[i]?.innerText?.trim() || '';
      const a = answers[i]?.innerText?.trim() || '';
      if (q.length >= 5 && a.length >= 10) {
        turns.push({ humanMessage: q, agentMessage: a });
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
      startObserver._debounce = setTimeout(processNewTurns, 3000);
    });
    observer.observe(target, { childList: true, subtree: true, characterData: true });
  }

  function init() {
    const check = setInterval(() => {
      if (document.querySelector('main, [class*="thread"]')) {
        clearInterval(check);
        const existing = extractTurns();
        lastProcessedIndex = existing.length - 1;
        startObserver();
        console.log('[0Latency] Perplexity capture active');
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
