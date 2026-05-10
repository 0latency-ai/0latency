import { mergeConfig, getApiKey } from './dist/config.js';
import { readFileSync } from 'fs';

const apiKey = getApiKey() || 'sk_test_key_for_init_12345';
const configPath = '/tmp/test-claude-config.json';

console.log('Testing config merge...');
console.log(`Using API key: ${apiKey.slice(0, 10)}...`);

mergeConfig(configPath, apiKey);
console.log(`✓ Config written to: ${configPath}`);

// Read and verify
const config = JSON.parse(readFileSync(configPath, 'utf-8'));
console.log('Config content:', JSON.stringify(config, null, 2));

if (config.mcpServers && config.mcpServers['0latency']) {
  console.log('✓ 0latency entry found in config');
  console.log('✓ Config merge test PASSED');
} else {
  console.error('❌ 0latency entry NOT found');
  process.exit(1);
}
