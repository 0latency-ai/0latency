#!/usr/bin/env node
/**
 * Progressive Stress Test — finds breaking points
 * Ramps from 10 → 50 → 100 → 250 → 500 → 1000 → 5000 → 10000 concurrent
 * Reports where latency degrades and where errors start
 */

const BASE = process.env.API_URL || 'http://127.0.0.1:8420';
const API_KEY = process.env.API_KEY || '';

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

const STAGES = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000];
const REQUESTS_PER_STAGE = 200; // total requests per stage (split across workers)

async function makeRequest(endpoint) {
  const start = Date.now();
  try {
    let url, opts;
    
    if (endpoint === 'health') {
      url = `${BASE}/health`;
      opts = { method: 'GET', signal: AbortSignal.timeout(10000) };
    } else if (endpoint === 'list') {
      url = `${BASE}/memories?agent_id=stresstest&limit=5`;
      opts = { method: 'GET', headers, signal: AbortSignal.timeout(10000) };
    } else if (endpoint === 'search') {
      url = `${BASE}/memories/search?agent_id=stresstest&q=test`;
      opts = { method: 'GET', headers, signal: AbortSignal.timeout(10000) };
    } else if (endpoint === 'recall') {
      url = `${BASE}/recall`;
      opts = {
        method: 'POST', headers,
        body: JSON.stringify({ agent_id: 'stresstest', conversation_context: 'test query', budget_tokens: 1000 }),
        signal: AbortSignal.timeout(15000),
      };
    }
    
    const res = await fetch(url, opts);
    const latency = Date.now() - start;
    return { ok: res.ok, status: res.status, latency };
  } catch (err) {
    return { ok: false, status: 0, latency: Date.now() - start, error: err.message?.substring(0, 50) };
  }
}

function percentile(arr, p) {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  return sorted[Math.ceil(sorted.length * p / 100) - 1] || 0;
}

async function runStage(concurrency) {
  // Focus on read-heavy endpoints (realistic — most users read, few write)
  const endpoints = [];
  const reqsPerWorker = Math.max(1, Math.floor(REQUESTS_PER_STAGE / concurrency));
  
  for (let i = 0; i < REQUESTS_PER_STAGE; i++) {
    const r = Math.random();
    if (r < 0.4) endpoints.push('health');       // 40% health
    else if (r < 0.7) endpoints.push('list');     // 30% list
    else if (r < 0.9) endpoints.push('search');   // 20% search
    else endpoints.push('recall');                 // 10% recall (heaviest)
  }
  
  const startTime = Date.now();
  const results = [];
  let idx = 0;
  
  // Launch requests in batches of `concurrency`
  while (idx < endpoints.length) {
    const batch = endpoints.slice(idx, idx + concurrency);
    const batchResults = await Promise.all(batch.map(ep => makeRequest(ep)));
    results.push(...batchResults);
    idx += concurrency;
  }
  
  const elapsed = (Date.now() - startTime) / 1000;
  const latencies = results.filter(r => r.latency > 0).map(r => r.latency);
  const successes = results.filter(r => r.ok).length;
  const errors = results.filter(r => !r.ok).length;
  const rateLimit = results.filter(r => r.status === 429).length;
  
  return {
    concurrency,
    total: results.length,
    successes,
    errors,
    rateLimit,
    rps: (results.length / elapsed).toFixed(1),
    elapsed: elapsed.toFixed(1),
    p50: percentile(latencies, 50),
    p95: percentile(latencies, 95),
    p99: percentile(latencies, 99),
    max: Math.max(...latencies, 0),
    errorRate: ((errors / results.length) * 100).toFixed(1),
  };
}

async function run() {
  console.log('');
  console.log('╔══════════════════════════════════════════════════════════════════════════╗');
  console.log('║              0LATENCY STRESS TEST — PROGRESSIVE LOAD RAMP              ║');
  console.log('╚══════════════════════════════════════════════════════════════════════════╝');
  console.log(`  Target:  ${BASE}`);
  console.log(`  API Key: ${API_KEY ? 'set' : 'NOT SET (health-only mode)'}`);
  console.log(`  Stages:  ${STAGES.join(' → ')} concurrent`);
  console.log(`  Reqs/stage: ${REQUESTS_PER_STAGE}`);
  console.log('');
  console.log('┌────────────┬───────┬─────────┬────────┬───────┬───────┬───────┬──────────┐');
  console.log('│ Concurrent │ Total │ Success │ Errors │ p50   │ p95   │ p99   │ RPS      │');
  console.log('├────────────┼───────┼─────────┼────────┼───────┼───────┼───────┼──────────┤');
  
  const allResults = [];
  let broke = false;
  
  for (const concurrency of STAGES) {
    const result = await runStage(concurrency);
    allResults.push(result);
    
    const status = result.errors > result.total * 0.5 ? '💥' : 
                   result.errors > result.total * 0.1 ? '⚠️ ' : 
                   result.p95 > 5000 ? '🐌' : '✅';
    
    console.log(
      `│ ${String(concurrency).padStart(10)} │ ${String(result.total).padStart(5)} │ ` +
      `${String(result.successes).padStart(7)} │ ${String(result.errors).padStart(6)} │ ` +
      `${String(result.p50 + 'ms').padStart(5)} │ ${String(result.p95 + 'ms').padStart(5)} │ ` +
      `${String(result.p99 + 'ms').padStart(5)} │ ${(result.rps + '/s').padStart(8)} │ ${status}`
    );
    
    // Stop if >80% error rate
    if (parseFloat(result.errorRate) > 80) {
      console.log('├────────────┴───────┴─────────┴────────┴───────┴───────┴───────┴──────────┤');
      console.log(`│  💥 STOPPED: ${result.errorRate}% error rate at ${concurrency} concurrent`.padEnd(75) + '│');
      broke = true;
      break;
    }
    
    // Brief cooldown between stages
    await new Promise(r => setTimeout(r, 2000));
  }
  
  console.log('└────────────┴───────┴─────────┴────────┴───────┴───────┴───────┴──────────┘');
  
  // Summary
  console.log('');
  console.log('ANALYSIS:');
  
  const lastGood = allResults.filter(r => parseFloat(r.errorRate) < 10);
  const firstBad = allResults.find(r => parseFloat(r.errorRate) >= 10);
  
  if (lastGood.length > 0) {
    const best = lastGood[lastGood.length - 1];
    console.log(`  ✅ Handles ${best.concurrency} concurrent users reliably (${best.errorRate}% errors, p95=${best.p95}ms)`);
  }
  
  if (firstBad) {
    console.log(`  ⚠️  Degrades at ${firstBad.concurrency} concurrent (${firstBad.errorRate}% errors, p95=${firstBad.p95}ms)`);
  }
  
  console.log('');
  console.log('SCALING RECOMMENDATIONS:');
  console.log('  • 100 users  → Current 2GB droplet is fine');
  console.log('  • 1,000 users → 4GB droplet + 4 uvicorn workers ($24/mo)');
  console.log('  • 10,000 users → fly.io auto-scaling (2-8 containers) ($50-100/mo)');
  console.log('  • 100,000 users → Kubernetes + managed Postgres ($500+/mo)');
  console.log('');
}

run().catch(console.error);
