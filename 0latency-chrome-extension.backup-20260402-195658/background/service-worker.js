/**
 * Background Service Worker
 * Handles API communication with 0Latency
 */

import { ZeroLatencyClient } from './api-client.js';
import { AuthManager } from './auth.js';

// Message handler
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'storeMemories') {
    handleStoreMemories(request.payload)
      .then(result => sendResponse({ success: true, result }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true; // Keep channel open for async response
  }

  if (request.action === 'validateApiKey') {
    handleValidateApiKey(request.payload.apiKey)
      .then(valid => sendResponse({ success: true, valid }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }

  if (request.action === 'getStatus') {
    handleGetStatus()
      .then(status => sendResponse({ success: true, status }))
      .catch(error => sendResponse({ success: false, error: error.message }));
    return true;
  }
});

/**
 * Store memories to 0Latency API
 */
async function handleStoreMemories(payload) {
  const { platform, conversationId, messages } = payload;

  // Get API key
  const apiKey = await AuthManager.getApiKey();
  if (!apiKey) {
    throw new Error('No API key configured');
  }

  // Initialize client
  const client = new ZeroLatencyClient(apiKey);

  // Format messages for 0Latency
  const memories = messages.map(msg => ({
    text: `${msg.role === 'user' ? 'User' : 'Assistant'}: ${msg.text}`,
    metadata: {
      platform: platform,
      conversation_id: conversationId,
      message_id: msg.id,
      role: msg.role,
      timestamp: msg.timestamp,
      ...msg.metadata
    }
  }));

  // Store to API
  if (memories.length === 1) {
    return await client.storeMemory(memories[0]);
  } else {
    return await client.storeMemories(memories);
  }
}

/**
 * Validate API key
 */
async function handleValidateApiKey(apiKey) {
  const client = new ZeroLatencyClient(apiKey);
  return await client.validateKey();
}

/**
 * Get extension status
 */
async function handleGetStatus() {
  const isAuthenticated = await AuthManager.isAuthenticated();
  const settings = await AuthManager.getSettings();

  return {
    isAuthenticated,
    settings,
    version: chrome.runtime.getManifest().version
  };
}

// Initialize on install
chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason === 'install') {
    console.log('[0Latency] Extension installed');
    
    // Open onboarding page
    chrome.tabs.create({
      url: 'popup/popup.html'
    });
  }
  
  if (details.reason === 'update') {
    console.log('[0Latency] Extension updated to', chrome.runtime.getManifest().version);
  }
});

console.log('[0Latency] Background service worker initialized');
