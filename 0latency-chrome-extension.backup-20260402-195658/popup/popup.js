/**
 * Popup UI Logic
 */

// DOM Elements
const statusEl = document.getElementById('status');
const statusTextEl = document.getElementById('status-text');
const errorEl = document.getElementById('error');
const authSection = document.getElementById('auth-section');
const settingsSection = document.getElementById('settings-section');
const apiKeyInput = document.getElementById('api-key');
const agentIdInput = document.getElementById('agent-id');
const connectBtn = document.getElementById('connect-btn');
const disconnectBtn = document.getElementById('disconnect-btn');
const toggles = document.querySelectorAll('.toggle');

// Initialize
initPopup();

async function initPopup() {
  try {
    // Check if already authenticated
    const apiKey = await getApiKey();
    
    if (apiKey) {
      // Validate stored key
      const isValid = await validateApiKey(apiKey);
      if (isValid) {
        showConnectedState();
        await loadSettings();
      } else {
        showDisconnectedState();
        showError('Stored API key is invalid. Please re-enter.');
      }
    } else {
      showDisconnectedState();
    }
  } catch (error) {
    console.error('Init error:', error);
    showError('Failed to initialize extension');
  }
}

// Event Listeners
connectBtn.addEventListener('click', async () => {
  const apiKey = apiKeyInput.value.trim();
  
  if (!apiKey) {
    showError('Please enter an API key');
    return;
  }

  connectBtn.disabled = true;
  connectBtn.textContent = 'Connecting...';
  hideError();

  try {
    // Validate key
    const isValid = await validateApiKey(apiKey);
    
    if (isValid) {
      // Store key
      await setApiKey(apiKey);
      showConnectedState();
      await loadSettings();
    } else {
      showError('Invalid API key. Please check and try again.');
    }
  } catch (error) {
    showError('Connection failed: ' + error.message);
  } finally {
    connectBtn.disabled = false;
    connectBtn.textContent = 'Connect';
  }
});

disconnectBtn.addEventListener('click', async () => {
  if (confirm('Disconnect from 0Latency? You can reconnect anytime.')) {
    await clearApiKey();
    showDisconnectedState();
    apiKeyInput.value = '';
  }
});

// Agent ID input handler
agentIdInput.addEventListener('change', async () => {
  const agentId = agentIdInput.value.trim() || 'justin';
  await updateAgentId(agentId);
});

// Platform toggles
toggles.forEach(toggle => {
  toggle.addEventListener('click', async () => {
    toggle.classList.toggle('active');
    const platform = toggle.dataset.platform;
    const enabled = toggle.classList.contains('active');
    await updatePlatformSetting(platform, enabled);
  });
});

// Helper Functions
function showConnectedState() {
  statusEl.className = 'status status-connected';
  statusTextEl.textContent = 'Connected to 0Latency';
  authSection.classList.add('hidden');
  settingsSection.classList.remove('hidden');
}

function showDisconnectedState() {
  statusEl.className = 'status status-disconnected';
  statusTextEl.textContent = 'Not connected';
  authSection.classList.remove('hidden');
  settingsSection.classList.add('hidden');
}

function showError(message) {
  errorEl.textContent = message;
  errorEl.classList.remove('hidden');
}

function hideError() {
  errorEl.classList.add('hidden');
}

async function loadSettings() {
  const result = await chrome.storage.sync.get(['zl_settings']);
  const settings = result['zl_settings'] || {
    agent_id: 'justin',
    platforms: {
      chatgpt: true,
      claude: true,
      gemini: true
    }
  };

  // Update agent ID field
  agentIdInput.value = settings.agent_id || 'justin';

  // Update toggle states
  toggles.forEach(toggle => {
    const platform = toggle.dataset.platform;
    if (settings.platforms[platform]) {
      toggle.classList.add('active');
    } else {
      toggle.classList.remove('active');
    }
  });
}

async function updateAgentId(agentId) {
  const result = await chrome.storage.sync.get(['zl_settings']);
  const settings = result['zl_settings'] || {
    platforms: {}
  };

  settings.agent_id = agentId;
  await chrome.storage.sync.set({ 'zl_settings': settings });
  console.log('[0Latency] Agent ID updated to:', agentId);
}

async function updatePlatformSetting(platform, enabled) {
  const result = await chrome.storage.sync.get(['zl_settings']);
  const settings = result['zl_settings'] || {
    platforms: {}
  };

  settings.platforms[platform] = enabled;
  await chrome.storage.sync.set({ 'zl_settings': settings });
}

// Chrome Storage Helpers
async function getApiKey() {
  const result = await chrome.storage.local.get(['zl_api_key']);
  return result['zl_api_key'] || null;
}

async function setApiKey(apiKey) {
  await chrome.storage.local.set({ 'zl_api_key': apiKey });
}

async function clearApiKey() {
  await chrome.storage.local.remove(['zl_api_key']);
}

// API Validation
async function validateApiKey(apiKey) {
  try {
    const response = await chrome.runtime.sendMessage({
      action: 'validateApiKey',
      payload: { apiKey }
    });
    return response.success && response.valid;
  } catch (error) {
    console.error('Validation error:', error);
    return false;
  }
}
