/**
 * k6 Smoke Test — Zero Latency Memory API
 * Run: k6 run load-tests/k6-smoke.js
 * Or without k6: node load-tests/load-test.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const extractLatency = new Trend('extract_latency', true);
const recallLatency = new Trend('recall_latency', true);
const listLatency = new Trend('list_latency', true);

const BASE_URL = __ENV.API_URL || 'http://127.0.0.1:8420';
const API_KEY = __ENV.API_KEY || '';

export const options = {
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
    },
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 20 },
        { duration: '30s', target: 0 },
      ],
      startTime: '35s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<2000'],  // 95% under 2s
    errors: ['rate<0.1'],               // <10% error rate
    extract_latency: ['p(95)<3000'],    // Extract under 3s (includes LLM call)
    recall_latency: ['p(95)<1000'],     // Recall under 1s
    list_latency: ['p(95)<500'],        // List under 500ms
  },
};

const headers = {
  'Content-Type': 'application/json',
  'X-API-Key': API_KEY,
};

export default function () {
  const scenario = Math.random();

  if (scenario < 0.3) {
    // 30% — Health check (no auth)
    const res = http.get(`${BASE_URL}/health`);
    check(res, { 'health 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  } else if (scenario < 0.5) {
    // 20% — List memories
    const start = Date.now();
    const res = http.get(`${BASE_URL}/memories?agent_id=loadtest&limit=20`, { headers });
    listLatency.add(Date.now() - start);
    check(res, { 'list 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  } else if (scenario < 0.7) {
    // 20% — Search
    const queries = ['financial', 'project', 'decision', 'preference', 'task'];
    const q = queries[Math.floor(Math.random() * queries.length)];
    const res = http.get(`${BASE_URL}/memories/search?agent_id=loadtest&q=${q}`, { headers });
    check(res, { 'search 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  } else if (scenario < 0.85) {
    // 15% — Recall
    const contexts = [
      'What are the user preferences?',
      'Tell me about recent decisions',
      'What projects are active?',
      'Communication style preferences',
    ];
    const ctx = contexts[Math.floor(Math.random() * contexts.length)];
    const start = Date.now();
    const res = http.post(`${BASE_URL}/recall`, JSON.stringify({
      agent_id: 'loadtest',
      conversation_context: ctx,
      budget_tokens: 2000,
    }), { headers });
    recallLatency.add(Date.now() - start);
    check(res, { 'recall 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  } else {
    // 15% — Extract
    const messages = [
      ['I prefer dark mode in all apps', 'Noted, dark mode preference saved'],
      ['The project deadline is next Friday', 'Got it, deadline is next Friday'],
      ['Use TypeScript for the new service', 'Will use TypeScript for the new service'],
    ];
    const msg = messages[Math.floor(Math.random() * messages.length)];
    const start = Date.now();
    const res = http.post(`${BASE_URL}/extract`, JSON.stringify({
      agent_id: 'loadtest',
      human_message: msg[0],
      agent_message: msg[1],
    }), { headers });
    extractLatency.add(Date.now() - start);
    check(res, { 'extract 200': (r) => r.status === 200 });
    errorRate.add(res.status !== 200);
  }

  sleep(0.5 + Math.random());
}
