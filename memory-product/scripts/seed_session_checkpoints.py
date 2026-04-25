#!/usr/bin/env python3
"""
CP7b Phase 1: Seed script with MAXIMUM content variation.
Each checkpoint gets completely unique narrative and technical details.
"""
import uuid
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.chdir(os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from src.storage_multitenant import store_memories, set_tenant_context

NUM_CHECKPOINTS = 20
NUM_PROJECTS = 3
CHECKPOINT_TYPES = ['mid_thread', 'end_of_thread', 'auto_resume_meta', 'tail_recovery']
SOURCES = ['server_job', 'agent', 'extension']

# HIGHLY VARIED content templates
CONTENT_VARIATIONS = [
    """Detailed technical analysis of Redis connection pooling strategies. Evaluated maxclients=10000 vs connection multiplexing. Benchmark results: 15K req/s with pool vs 8K without. Memory overhead +120MB. Team consensus: implement pooling with retry backoff. Risk: pool exhaustion under load spike. Mitigation: circuit breaker pattern. Next: prototype in staging environment. Dependencies: update redis-py to 4.5.x, configure sentinel for HA.""",
    
    """Database schema migration plan for user_preferences table. Adding JSONB column for feature flags (estimated 2KB/user). Index strategy: GIN on jsonb_path_ops for containment queries. Migration steps: 1) Add column (no lock), 2) Backfill batch (1000 rows/sec), 3) Switch reads, 4) Drop old columns. Rollback: keep old schema 7 days. Performance impact: +5ms p95 query latency acceptable. Stakeholder approval needed from Product team.""",
    
    """Frontend refactoring: migrated 47 class components to hooks. Bundle size reduced 18KB (gzipped). Performance metrics improved: FCP -120ms, LCP -340ms. Breaking change: removed legacy PropTypes, added TypeScript strict mode. Test coverage 94% -> 91% (3 edge cases need rewrites). Deploy strategy: feature flag rollout 10% -> 50% -> 100% over 3 days. Monitoring: track error rate via Sentry.""",
    
    """API rate limiting implementation using sliding window algorithm. Token bucket rejected due to burst handling issues. Redis sorted sets for window tracking (expire after 60s). Limits: Free=20/min, Pro=100/min, Enterprise=500/min. Edge cases: handle clock skew, distributed counter race conditions. Solution: Lua script for atomic increment-check. Load test results: 50K req/s sustained, 0.3ms p99 overhead.""",
    
    """Security audit remediation: fixed 3 critical, 7 high, 12 medium findings. Critical items: SQL injection in /admin/export (parameterized queries added), XSS in user profiles (DOMPurify integration), IDOR in document access (added authorization middleware). High: CSRF tokens, helmet.js headers, secrets rotation. Timeline: deploy patches within 48h, notify affected users, file CVE if needed.""",
    
    """Async job queue architecture using BullMQ + Redis. Queue priorities: critical (SLA 5s), high (30s), normal (5min), low (best effort). Concurrency: 20 workers per queue type. Failure handling: exponential backoff (1s, 2s, 4s, 8s, 16s), max 5 retries, DLQ after exhaustion. Monitoring: Prometheus metrics for queue depth, processing time, error rate. Cost: +5/mo Redis instance.""",
    
    """WebSocket connection management redesign. Current: 1 connection/user, memory leak after 2h. New: connection pool with heartbeat (30s ping/pong), auto-reconnect with exponential backoff. Handle edge cases: multiple tabs, network flakiness, server restart. Scale testing: 10K concurrent connections, 2GB RAM, CPU 15%. Libraries evaluated: Socket.io (chosen), WS, uWebSockets. Migration: backward compatible protocol.""",
    
    """CI/CD pipeline optimization reduced deploy time from 18min to 7min. Changes: parallel test execution (4 runners), Docker layer caching, incremental builds. Cost: GitHub Actions minutes usage +40%, but deploy frequency +200%. Added: automatic rollback on health check failure, deployment notifications to Slack, canary releases for prod. Next: add smoke tests, E2E suite in separate workflow.""",
    
    """Monitoring system upgrade: migrated from custom solution to Datadog. Metrics: API latency (p50/p90/p99), error rates, throughput, DB query time. Alerts configured: error rate >1% (PagerDuty), latency p99 >1s (Slack), disk >85% (email). Dashboard includes: service map, request traces, log correlation. Training: 3 team sessions scheduled. Budget: 80/month for 15 hosts.""",
    
    """Load balancer configuration tuning for better traffic distribution. Algorithm: changed from round-robin to least-connections. Health checks: HTTP /health every 5s, 2 consecutive fails = unhealthy, 3 success = healthy. SSL termination at LB, backend HTTP. Connection draining: 30s timeout during deploys. Added: sticky sessions via cookie, rate limiting at LB layer. Result: 99.97% uptime last quarter.""",
    
    """Database query optimization: index analysis revealed 47 missing indexes causing table scans. Top offenders: user_events(created_at, user_id), transactions(status, updated_at). Created composite indexes, query time reduced 850ms -> 15ms. Postgres autovacuum tuning: reduced aggressive threshold. Analyzed query patterns: 80% read, 20% write. Considered: read replicas for analytics queries (deferred for Q2).""",
    
    """Authentication system refactor: JWT migration from custom to Auth0. Benefits: OAuth2 support, MFA built-in, security patches managed. Migration plan: dual-write period 2 weeks, then cutover. Token expiry: access 15min, refresh 7 days, rotation on use. Revocation: Redis blacklist for logout. Breaking change: new token format requires SDK update. Communication: email users 1 week before, in-app banner.""",
    
    """Feature flag system implemented using LaunchDarkly. Use cases: gradual rollouts, A/B tests, emergency kill switches. Flags created: new_checkout_flow (10% rollout), dark_mode_beta (opt-in), legacy_api_deprecation (targeting old clients). SDK integration: React hooks, server-side evaluation. Monitoring: track flag evaluation latency, fallback when unreachable. Cost: 0/month for 25K MAU tier.""",
    
    """Cache invalidation strategy redesigned: previous LRU policy caused stampede on expiry. New: probabilistic early expiration, stale-while-revalidate pattern. Cache layers: CDN (CloudFlare, 1h TTL), App (Redis, 5min TTL), DB (query cache, 30s TTL). Invalidation: tag-based purging on mutations. Metrics: hit rate 87% -> 94%, origin requests -60%. Edge cases: handle cache poisoning, race conditions.""",
    
    """API versioning strategy: migrated to URL-based (/v1, /v2). v1: deprecated but maintained 6 months. v2: breaking changes listed (renamed fields, new auth). Client migration: SDKs auto-upgraded, manual integrations need update. Docs: migration guide published, changelog detailed. Monitoring: track v1 usage, send deprecation warnings in response headers. Sunset date: v1 end-of-life Sept 30.""",
    
    """Container orchestration migration: Docker Compose -> Kubernetes. Cluster config: 3 nodes (4CPU, 16GB each), auto-scaling based on CPU >70%. Deployment: rolling updates, health checks, resource limits (CPU 500m-2, memory 512Mi-2Gi). Services: API (6 replicas), workers (3), Redis (1), Postgres (external). Monitoring: Prometheus + Grafana. Migration weekend: staged rollout, rollback plan ready.""",
    
    """Error handling middleware implemented: centralized exception handling, structured logging. Error types: ValidationError (400), AuthError (401), NotFoundError (404), RateLimitError (429), ServerError (500). Response format: {error, message, code, requestId}. Sentry integration: capture stack traces, user context, breadcrumbs. Alerts: >100 errors/5min triggers PagerDuty. Implemented: retry logic for transient failures.""",
    
    """GraphQL API design: evaluated vs REST, decision matrix created. Pros: flexible queries, typed schema, single endpoint. Cons: caching complexity, N+1 queries. Implementation: Apollo Server, DataLoader for batching. Schema: 15 types, 8 queries, 6 mutations. Authentication: JWT in headers. Rate limiting: query complexity analysis. Performance: resolver optimization, persistent queries. Rollout: beta endpoints, gather feedback.""",
    
    """Backup and disaster recovery plan: RTO 4h, RPO 1h. Automated backups: DB snapshot every 6h (retained 30 days), incremental WAL archiving. Testing: monthly restore drills, documented runbooks. Geographic redundancy: backups replicated to 3 regions. Scenarios covered: data corruption, accidental deletion, region failure, ransomware. Recovery steps: 1) assess, 2) restore from snapshot, 3) replay WAL, 4) verify integrity.""",
    
    """Performance testing framework established: k6 for load tests, Lighthouse for frontend. Test scenarios: sustained load (1K RPS for 10min), spike (0-5K RPS in 30s), soak (500 RPS for 4h). Metrics: response time, error rate, throughput, resource usage. CI integration: run on every PR merge, block deploy if p95 >500ms. Results tracked: week-over-week comparison, regression alerts. Budget: dedicated test environment 20/month.""",
]

TEST_TENANT_ID = None

def get_or_create_test_tenant():
    global TEST_TENANT_ID
    import psycopg2
    conn_string = os.environ.get('MEMORY_DB_CONN')
    conn = psycopg2.connect(conn_string)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM memory_service.tenants ORDER BY created_at LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    if row:
        TEST_TENANT_ID = str(row[0])
        print(f"Using tenant: {TEST_TENANT_ID}")
    else:
        print("ERROR: No tenants found")
        sys.exit(1)
    return TEST_TENANT_ID

def main():
    print("CP7b Phase 1: Seed Script (Maximum Variation)")
    print("=" * 50)
    
    tenant_id = get_or_create_test_tenant()
    set_tenant_context(tenant_id)
    
    # Generate 3 projects
    projects = []
    for i in range(NUM_PROJECTS):
        projects.append({
            "id": str(uuid.uuid4()),
            "name": f"Project-{chr(65+i)}-TestData",
        })
    
    # Generate 20 checkpoints with UNIQUE content
    checkpoints = []
    checkpoint_types_dist = [0, 0, 0, 0]
    
    for i in range(NUM_CHECKPOINTS):
        project = projects[i % NUM_PROJECTS]
        
        # Ensure type coverage
        if i < 4:
            checkpoint_type = CHECKPOINT_TYPES[i]
            checkpoint_types_dist[i] += 1
        else:
            type_idx = random.choices([0,1,2,3], weights=[60,20,10,10], k=1)[0]
            checkpoint_type = CHECKPOINT_TYPES[type_idx]
            checkpoint_types_dist[type_idx] += 1
        
        thread_id = str(uuid.uuid4())
        thread_title = f"Thread-{i+1}-{project['name']}-{checkpoint_type}"
        sequence = (i % 5) + 1
        start_turn = sequence * 20 - 19
        end_turn = sequence * 20
        
        # Use COMPLETELY UNIQUE content from variations list
        # Add random technical numbers and project/thread identifiers
        unique_content = f"""CHECKPOINT #{i+1} - {checkpoint_type.upper()}
Thread: {thread_title} (ID: {thread_id})
Project: {project['name']} (ID: {project['id']})
Turns: {start_turn}-{end_turn} | Sequence: {sequence}

TECHNICAL DETAILS:
{CONTENT_VARIATIONS[i % len(CONTENT_VARIATIONS)]}

CONTEXT HASH: {uuid.uuid4()}
TIMESTAMP: 2026-04-23T{18+(i//3)}:{(i*3)%60:02d}:00Z
UNIQUE MARKER: checkpoint-{i}-variant-{random.randint(1000,9999)}
"""
        
        parent_memory_ids = [str(uuid.uuid4()) for _ in range(random.randint(3, 12))]
        
        memory = {
            "agent_id": tenant_id,
            "headline": f"CP-{i+1}: {checkpoint_type} for {project['name']} (Thread {thread_id[:8]}, Turns {start_turn}-{end_turn})",
            "context": unique_content[:300],
            "full_content": unique_content,
            "memory_type": "session_checkpoint",
            "importance": 0.7,
            "confidence": 0.9,
            "entities": [],
            "categories": ["checkpoint", checkpoint_type, f"project-{i%3}"],
            "scope": "/",
            "source_session": f"thread_{thread_id}",
            "source_turn": None,
            "metadata": {
                "level": 1,
                "thread_id": thread_id,
                "project_id": project["id"],
                "thread_title": thread_title,
                "project_name": project["name"],
                "checkpoint_sequence": sequence,
                "checkpoint_type": checkpoint_type,
                "turn_range": [start_turn, end_turn],
                "turn_count": 20,
                "time_span_seconds": random.randint(600, 3600),
                "parent_memory_ids": parent_memory_ids,
                "child_memory_ids": [],
                "parent_checkpoint_id": None,
                "source": random.choice(SOURCES)
            },
        }
        
        checkpoints.append(memory)
        print(f"  {i+1:2d}. {checkpoint_type:20s} | {project['name']:20s} | unique_marker: cp-{i}")
    
    print(f"\nStoring {NUM_CHECKPOINTS} checkpoints...")
    
    result = store_memories(checkpoints, tenant_id)
    
    print(f"\n✓ Stored {len(result['ids'])} checkpoints")
    print(f"  New: {len(result['new_ids'])}")
    print(f"  Deduplicated: {len(result['deduplicated_ids'])}")
    
    if len(result['new_ids']) != NUM_CHECKPOINTS:
        print(f"\n✗ ERROR: Expected {NUM_CHECKPOINTS} new, got {len(result['new_ids'])}")
        sys.exit(1)
    
    # Verify
    import psycopg2
    conn = psycopg2.connect(os.environ.get('MEMORY_DB_CONN'))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM memory_service.memories 
        WHERE memory_type = 'session_checkpoint' 
          AND agent_id = %s AND superseded_at IS NULL
    """, (tenant_id,))
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    print(f"\n✓ Verified: {count} session_checkpoint records in database")
    
    if count == NUM_CHECKPOINTS:
        print(f"\n✓ SUCCESS: All {NUM_CHECKPOINTS} unique checkpoints stored")
        print(f"  mid_thread: {checkpoint_types_dist[0]}")
        print(f"  end_of_thread: {checkpoint_types_dist[1]}")
        print(f"  auto_resume_meta: {checkpoint_types_dist[2]}")
        print(f"  tail_recovery: {checkpoint_types_dist[3]}")
    else:
        print(f"\n✗ ERROR: Count mismatch")
        sys.exit(1)

if __name__ == "__main__":
    main()
