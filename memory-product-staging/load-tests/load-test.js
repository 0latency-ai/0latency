#!/usr/bin/env node
/**
 * Lightweight load test (no k6 required)
 * Run: API_KEY=zl_live_... node load-tests/load-test.js
 */

const BASE = process.env.API_URL || 'http://127.0.0.1:8420';
const API_KEY = process.env.API_KEY || '';
const DURATION_S = parseInt(process.env.DURATION || '30', 10);
const CONCURRENCY = parseInt(process.env.CONCURRENCY || '5', 10);

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

const results = { total: 0, success: 0, errors: 0, latencies: [] };
const endpointStats = {};

async function makeRequest(name, method, path, body) {
  const url = `${BASE}${path}`;
  const start = Date.now();
  
  try {
    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);
    
    const res = await fetch(url, opts);
    const latency = Date.now() - start;
    
    results.total++;
    results.latencies.push(latency);
    
    if (!endpointStats[name]) endpointStats[name] = { count: 0, latencies: [], errors: 0 };
    endpointStats[name].count++;
    endpointStats[name].latencies.push(latency);
    
    if (res.ok) {
      results.success++;
    } else {
      results.errors++;
      endpointStats[name].errors++;
    }
    
    return latency;
  } catch (err) {
    results.total++;
    results.errors++;
    if (!endpointStats[name]) endpointStats[name] = { count: 0, latencies: [], errors: 0 };
    endpointStats[name].errors++;
    return -1;
  }
}

async function worker(id) {
  const deadline = Date.now() + DURATION_S * 1000;
  
  while (Date.now() < deadline) {
    const r = Math.random();
    
    if (r < 0.3) {
      await makeRequest('health', 'GET', '/health');
    } else if (r < 0.5) {
      await makeRequest('list', 'GET', '/memories?agent_id=loadtest&limit=20');
    } else if (r < 0.7) {
      await makeRequest('search', 'GET', '/memories/search?agent_id=loadtest&q=test');
    } else if (r < 0.85) {
      await makeRequest('recall', 'POST', '/recall', {
        agent_id: 'loadtest',
        conversation_context: 'What are the user preferences?',
        budget_tokens: 2000,
      });
    } else {
      await makeRequest('extract', 'POST', '/extract', {
        agent_id: 'loadtest',
        human_message: 'Test message ' + Date.now(),
        agent_message: 'Acknowledged test message',
      });
    }
    
    await new Promise(r => setTimeout(r, 200 + Math.random() * 500));
  }
}

function percentile(arr, p) {
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.ceil(sorted.length * p / 100) - 1;
  return sorted[Math.max(0, idx)];
}

async function run() {
  console.log(`\n🔥 Load Test — ${CONCURRENCY} workers × ${DURATION_S}s`);
  console.log(`   Target: ${BASE}`);
  console.log(`   API Key: ${API_KEY ? 'set' : 'NOT SET'}\n`);
  
  const start = Date.now();
  
  // Launch workers
  const workers = [];
  for (let i = 0; i < CONCURRENCY; i++) {
    workers.push(worker(i));
  }
  
  await Promise.all(workers);
  
  const elapsed = (Date.now() - start) / 1000;
  
  // Results
  console.log('═'.repeat(60));
  console.log('RESULTS');
  console.log('═'.repeat(60));
  console.log(`Duration:    ${elapsed.toFixed(1)}s`);
  console.log(`Total reqs:  ${results.total}`);
  console.log(`Success:     ${results.success} (${(results.success/results.total*100).toFixed(1)}%)`);
  console.log(`Errors:      ${results.errors} (${(results.errors/results.total*100).toFixed(1)}%)`);
  console.log(`RPS:         ${(results.total/elapsed).toFixed(1)}`);
  
  if (results.latencies.length > 0) {
    console.log(`\nLatency:`);
    console.log(`  p50:  ${percentile(results.latencies, 50)}ms`);
    console.log(`  p90:  ${percentile(results.latencies, 90)}ms`);
    console.log(`  p95:  ${percentile(results.latencies, 95)}ms`);
    console.log(`  p99:  ${percentile(results.latencies, 99)}ms`);
    console.log(`  max:  ${Math.max(...results.latencies)}ms`);
  }
  
  console.log(`\nPer Endpoint:`);
  for (const [name, stats] of Object.entries(endpointStats)) {
    const p95 = stats.latencies.length > 0 ? percentile(stats.latencies, 95) : 0;
    console.log(`  ${name.padEnd(10)} — ${stats.count} reqs, p95=${p95}ms, errors=${stats.errors}`);
  }
  
  console.log('═'.repeat(60));
  
  // Pass/fail
  const p95 = percentile(results.latencies, 95);
  const errorRate = results.errors / results.total;
  
  if (p95 > 2000) {
    console.log(`❌ FAIL: p95 latency ${p95}ms > 2000ms threshold`);
    process.exit(1);
  }
  if (errorRate > 0.1) {
    console.log(`❌ FAIL: error rate ${(errorRate*100).toFixed(1)}% > 10% threshold`);
    process.exit(1);
  }
  
  console.log(`✅ PASS: p95=${p95}ms, error rate=${(errorRate*100).toFixed(1)}%`);
}

run().catch(console.error);
