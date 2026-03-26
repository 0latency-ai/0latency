/**
 * Live API integration test
 * Run this to verify the SDK works against the real API
 */

import { Memory } from './src';

const API_KEY = process.env.ZEROLATENCY_API_KEY || '';

if (!API_KEY) {
  console.error('❌ ZEROLATENCY_API_KEY environment variable not set');
  process.exit(1);
}

async function testLiveAPI() {
  const memory = new Memory({ apiKey: API_KEY });
  const testAgentId = `sdk-test-${Date.now()}`;

  console.log('=== 0Latency SDK Live API Test ===\n');

  try {
    // Test 1: Health check
    console.log('1. Testing health endpoint...');
    const health = await memory.health();
    console.log('✓ Health check passed:', health);

    // Test 2: Add a memory
    console.log('\n2. Testing add() method...');
    const addResult = await memory.add('The SDK test user loves TypeScript', {
      agentId: testAgentId,
      metadata: { test: true, timestamp: Date.now() }
    });
    console.log('✓ Memory added:', addResult);

    // Test 3: Recall the memory
    console.log('\n3. Testing recall() method...');
    const recallResult = await memory.recall('What programming language does the user like?', {
      agentId: testAgentId,
      limit: 5
    });
    console.log('✓ Recall result:', JSON.stringify(recallResult, null, 2));

    // Test 4: Extract from conversation
    console.log('\n4. Testing extract() method...');
    const extractResult = await memory.extract([
      { role: 'user', content: 'I prefer using React for frontend development' },
      { role: 'assistant', content: 'React is a great choice for building UIs!' }
    ], { agentId: testAgentId });
    console.log('✓ Extract job started:', extractResult);

    if (extractResult.job_id) {
      console.log('\n5. Testing extractStatus() method...');
      const statusResult = await memory.extractStatus(extractResult.job_id);
      console.log('✓ Job status:', statusResult);
    }

    console.log('\n=== All tests passed! ===');
    console.log(`\nTest agent ID: ${testAgentId}`);
    console.log('You can query this agent to see stored memories.');

  } catch (error) {
    console.error('\n❌ Test failed:', error);
    if (error instanceof Error) {
      console.error('Error message:', error.message);
      console.error('Stack:', error.stack);
    }
    process.exit(1);
  }
}

testLiveAPI();
