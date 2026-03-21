/**
 * 0Latency Chrome Extension — Background Service Worker
 * Receives conversation turns from content scripts, sends to Memory API.
 */

const DEFAULT_API_URL = 'https://api.0latency.ai';
const EXTRACT_ENDPOINT = '/extract';
const RECALL_ENDPOINT = '/recall';

// Rate limiting — max 1 extraction per 10 seconds per tab
const lastExtraction = {};
const RATE_LIMIT_MS = 10000;

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'EXTRACT_TURN') {
    handleExtraction(message.data, sender.tab?.id)
      .then(result => sendResponse({ success: true, result }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep channel open for async response
  }

  if (message.type === 'RECALL') {
    handleRecall(message.data)
      .then(result => sendResponse({ success: true, result }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === 'GET_STATUS') {
    getStatus().then(status => sendResponse(status));
    return true;
  }

  if (message.type === 'SET_CONFIG') {
    chrome.storage.sync.set(message.data, () => {
      sendResponse({ success: true });
    });
    return true;
  }
});

async function getConfig() {
  return new Promise(resolve => {
    chrome.storage.sync.get({
      apiKey: '',
      apiUrl: DEFAULT_API_URL,
      agentId: 'chrome-extension',
      autoCapture: true,
      capturedCount: 0,
    }, resolve);
  });
}

async function handleExtraction(data, tabId) {
  const config = await getConfig();
  if (!config.apiKey) throw new Error('API key not configured');
  if (!config.autoCapture) return { skipped: true, reason: 'auto-capture disabled' };

  // Rate limit per tab
  const now = Date.now();
  if (tabId && lastExtraction[tabId] && (now - lastExtraction[tabId]) < RATE_LIMIT_MS) {
    return { skipped: true, reason: 'rate limited' };
  }
  if (tabId) lastExtraction[tabId] = now;

  const { humanMessage, agentMessage, platform, sessionKey } = data;

  // Skip very short exchanges
  if (humanMessage.length < 20 && agentMessage.length < 50) {
    return { skipped: true, reason: 'exchange too short' };
  }

  const response = await fetch(`${config.apiUrl}${EXTRACT_ENDPOINT}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': config.apiKey,
    },
    body: JSON.stringify({
      agent_id: config.agentId,
      human_message: humanMessage,
      agent_message: agentMessage,
      session_key: `${platform}:${sessionKey || 'unknown'}`,
      turn_id: `${platform}:${Date.now()}`,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${response.status}`);
  }

  const result = await response.json();

  // Update captured count
  if (result.memories_stored > 0) {
    const current = await getConfig();
    chrome.storage.sync.set({
      capturedCount: (current.capturedCount || 0) + result.memories_stored,
    });

    // Badge update
    chrome.action.setBadgeText({ text: String(result.memories_stored), tabId });
    chrome.action.setBadgeBackgroundColor({ color: '#818cf8', tabId });
    setTimeout(() => chrome.action.setBadgeText({ text: '', tabId }), 3000);
  }

  return result;
}

async function handleRecall(data) {
  const config = await getConfig();
  if (!config.apiKey) throw new Error('API key not configured');

  const response = await fetch(`${config.apiUrl}${RECALL_ENDPOINT}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': config.apiKey,
    },
    body: JSON.stringify({
      agent_id: config.agentId,
      conversation_context: data.context,
      budget_tokens: data.budgetTokens || 4000,
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail || `API error ${response.status}`);
  }

  return response.json();
}

async function getStatus() {
  const config = await getConfig();
  let apiStatus = 'unknown';

  if (config.apiKey) {
    try {
      const r = await fetch(`${config.apiUrl}/health`, { timeout: 5000 });
      const data = await r.json();
      apiStatus = data.status || 'unknown';
    } catch {
      apiStatus = 'unreachable';
    }
  }

  return {
    configured: !!config.apiKey,
    apiStatus,
    agentId: config.agentId,
    autoCapture: config.autoCapture,
    capturedCount: config.capturedCount || 0,
  };
}
