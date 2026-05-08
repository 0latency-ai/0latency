# CP8 P5.4 — Diff Webhooks (Scope Document)

**Status:** Scope locked. Ready for CC build chain.
**Tier:** 2 (1 migration, additive, reversible).
**Wall-clock target:** 90–120 min CC execution.
**Dependencies:** P5.1 redaction cascade ✅ (synthesis versioning is what we hook).
**Master HEAD at scope time:** 25a3c43.
**Migration head at scope time:** b64d6554297a (027). This work adds 028.

---

## Goal

When a synthesis memory is replaced (forward-versioned via `superseded_by`), emit a signed HTTP POST to tenant-configured webhook URLs containing the diff: old content, new content, change reason, audit event ID. Retries with exponential backoff. Dead-letter on exhaustion.

Why: Tenants running 0Latency need to react to memory drift in their own systems (cache invalidation, agent re-prompting, downstream search index updates). This is the first outbound integration surface and a clear enterprise differentiator vs Mem0 (no webhooks).

---

## Locked Scope Decisions

### Decision 1 — Webhook config storage: dedicated `tenant_webhooks` table
**Rejected:** JSONB column on `tenants`. Forces a schema migration to add per-row toggles, can't index URL/active status, painful to track secret rotation history.
**Chosen:** Dedicated table `memory_service.tenant_webhooks`. Multiple rows per tenant. Per-row enable/disable. Forward-compat with CP13 `policies.audit_export`.

### Decision 2 — Dead-letter queue: dedicated `webhook_deliveries` table
**Rejected:** Reuse RQ worker queue. Tangles webhook lifecycle with memory extraction worker lifecycle, harder to audit, no SQL-queryable history.
**Chosen:** Dedicated table `memory_service.webhook_deliveries`. One row per attempt. Status enum: `pending` → `delivered` | `failed` | `dead`. Indexed for queryability. Foundation for future `GET /webhooks/deliveries` reader endpoint.

### Decision 3 — HMAC signing: ship in v1
**Rejected:** Defer. HMAC is trivial to add now, breaking change to add later (consumers code their verifier once).
**Chosen:** Per-webhook 32-byte secret stored in `tenant_webhooks.secret`. Stripe-format header:
X-0Latency-Signature: t=<unix_timestamp>,v1=<hex_sha256_hmac>
HMAC computed over `f"{t}.{raw_body}"`. Timestamp prevents replay. Consumers verify by recomputing and rejecting if `|now - t| > 300s`.

### Decision 4 — Retry budget: 5 attempts, exponential backoff
**Schedule:** `[60s, 300s, 1500s, 7200s, 43200s]` → cumulative ~14h envelope before dead-letter.
**Configurable later:** v1 ships hardcoded. CP13 introduces per-webhook retry override (Enterprise tier).

---

## Tier Matrix

Per CHECKPOINT-8-SCOPE-v3 Decision 3:

| Tier       | Webhook count | Configurable URL | HMAC | Retry config |
|------------|---------------|------------------|------|--------------|
| Free       | 0             | —                | —    | —            |
| Pro        | 0             | —                | —    | —            |
| Scale      | 1             | yes              | always on (auto-secret) | hardcoded |
| Enterprise | up to 10      | yes              | always on (rotatable)   | hardcoded v1, configurable in CP13 |

Enforced in endpoint handlers via existing `_require_tier_at_least` helper.

---

## Trigger Event (v1)

**Single event:** `synthesis.replaced`
**Fires when:** an UPDATE on `memory_service.memories` sets `superseded_by` from NULL to non-NULL on a row where `memory_type='synthesis'`.

Forward-extensible: payload always carries `event_type` field. Future v1.x can add `memory.redacted`, `decision.outcome_recorded`, etc., without payload schema breakage.

---

## Payload Schema (v1)

```json
{
  "event_id": "uuid",
  "event_type": "synthesis.replaced",
  "event_version": "1.0",
  "occurred_at": "2026-05-08T07:30:00.000Z",
  "tenant_id": "uuid",
  "agent_id": "string",
  "synthesis": {
    "memory_id": "uuid",
    "old_version": {
      "headline": "string",
      "context": "string",
      "full_content": "string",
      "created_at": "iso8601"
    },
    "new_version": {
      "memory_id": "uuid",
      "headline": "string",
      "context": "string",
      "full_content": "string",
      "created_at": "iso8601"
    },
    "change_reason": "string|null",
    "audit_event_id": "uuid|null"
  }
}
```

Notes:
- `event_id` is unique per emission (NOT per delivery attempt — same event_id is replayed across retries; consumers dedupe on it).
- `audit_event_id` references `synthesis_audit_events.id` if the supersession was audit-logged.
- Redaction-cascade-driven supersessions DO emit (consumers need to know content was scrubbed).

---

## Schema (Migration 028)

```sql
-- /alembic/versions/028_add_webhook_tables.py

CREATE TABLE memory_service.tenant_webhooks (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    name          text NOT NULL,
    url           text NOT NULL,
    secret        text NOT NULL,
    event_types   text[] NOT NULL DEFAULT ARRAY['synthesis.replaced'],
    enabled       boolean NOT NULL DEFAULT true,
    deleted_at    timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    last_success_at timestamptz,
    last_failure_at timestamptz,
    consecutive_failures integer NOT NULL DEFAULT 0,
    CONSTRAINT chk_webhook_url_https CHECK (url ~* '^https://'),
    CONSTRAINT chk_webhook_name_len  CHECK (char_length(name) BETWEEN 1 AND 100)
);

CREATE INDEX idx_tenant_webhooks_tenant_enabled
  ON memory_service.tenant_webhooks(tenant_id, enabled)
  WHERE enabled = true AND deleted_at IS NULL;

CREATE TABLE memory_service.webhook_deliveries (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id      uuid NOT NULL REFERENCES memory_service.tenant_webhooks(id) ON DELETE CASCADE,
    tenant_id       uuid NOT NULL REFERENCES memory_service.tenants(id) ON DELETE CASCADE,
    event_id        uuid NOT NULL,
    event_type      text NOT NULL,
    payload         jsonb NOT NULL,
    status          text NOT NULL DEFAULT 'pending',
    attempt_count   integer NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NOT NULL DEFAULT now(),
    last_attempt_at timestamptz,
    last_status_code integer,
    last_error      text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_delivery_status CHECK (status IN ('pending','delivered','failed','dead'))
);

CREATE INDEX idx_webhook_deliveries_due
  ON memory_service.webhook_deliveries(next_attempt_at)
  WHERE status = 'pending';

CREATE INDEX idx_webhook_deliveries_tenant_event
  ON memory_service.webhook_deliveries(tenant_id, event_id);

CREATE INDEX idx_webhook_deliveries_status_created
  ON memory_service.webhook_deliveries(status, created_at DESC);
```

Also extend `synthesis_audit_events.event_type` CHECK to include: `webhook_created`, `webhook_updated`, `webhook_deleted`, `webhook_auto_disabled`, `webhook_dead_lettered`. (Same pattern as P5.3 migration 027.)

**Tier classification:** Tier 2 (additive, reversible). Run autonomously via `bash scripts/db_migrate.sh up`. **No inner BEGIN/COMMIT in the SQL** (standing rule — would break dry-run wrapper).

**Down migration:** DROP TABLE both, in reverse order; revert audit event_type CHECK. Reversible.

---

## Endpoints (5 new, all `/webhooks/*`)

All Enterprise/Scale only. Tier check first, tenant isolation throughout.

### `POST /webhooks` — create webhook
**Body:**
```json
{
  "name": "prod-cache-invalidator",
  "url": "https://my-app.example.com/0latency-events",
  "event_types": ["synthesis.replaced"]
}
```
**Response 201:** `{ "id": "uuid", "name": "...", "url": "...", "secret": "<hex>", "enabled": true, "created_at": "..." }`
The secret is returned **once only** at creation. Subsequent reads omit it.

**Tier limit enforcement:** Scale = 1 active row max per tenant (count check WHERE deleted_at IS NULL before insert). Enterprise = 10 max.

### `GET /webhooks` — list tenant's active webhooks
Filter `WHERE deleted_at IS NULL`. Returns array. Secret field omitted. Response includes `consecutive_failures`, `last_success_at`, `last_failure_at` for ops visibility.

### `PATCH /webhooks/{id}` — update
Mutable fields: `name`, `url`, `enabled`, `event_types`. Not `secret` (use rotate endpoint).

### `POST /webhooks/{id}/rotate-secret` — Enterprise only
Generates new 32-byte secret, returns it once, persists. Old secret immediately invalidated. Use case: leaked secret remediation.

### `DELETE /webhooks/{id}` — soft delete
Sets `deleted_at = now()`. Row stays in `tenant_webhooks` forever; queries filter `WHERE deleted_at IS NULL`. In-flight `webhook_deliveries` rows are NOT cancelled — they finish their retry budget naturally. Audit-log via `webhook_deleted`.

---

## Emission Flow

### Where the trigger fires
Inside the synthesis writer code path, **after** the supersession UPDATE commits and **after** the audit event is written. Located in `api/synthesis.py` (CC: locate exact site via grep for `superseded_by` UPDATE).

### Enqueue helper
`enqueue_webhook_event` queries `tenant_webhooks` for enabled rows (deleted_at IS NULL, enabled=true) matching the tenant + event_type, INSERTs one `webhook_deliveries` row per matching webhook with `status='pending'`, `next_attempt_at=now()`. Returns immediately.

**Critical:** enqueue runs in the same DB transaction as the supersession write. If the transaction rolls back, no webhook is ever sent. Outbox-pattern correct.

### Worker (delivery loop)
**Reuse** existing `zerolatency-worker.service`. Add periodic job `process_webhook_queue`:
1. SELECT FOR UPDATE SKIP LOCKED rows from `webhook_deliveries` WHERE status='pending' AND next_attempt_at <= now() LIMIT 50
2. POST to webhook URL with HMAC-signed body, 10s timeout
3. On 2xx → status='delivered', last_status_code, increment webhook's last_success_at, reset consecutive_failures to 0
4. On non-2xx or timeout → increment attempt_count, set next_attempt_at via backoff schedule, status stays 'pending' (still retryable), increment webhook's consecutive_failures
5. If attempt_count >= 5 → status='dead', no more attempts. Audit-log `webhook_dead_lettered`.

**Cron cadence:** every 30s.

**Backoff:** `delays = [60, 300, 1500, 7200, 43200]` (seconds). `next_attempt_at = now() + delays[attempt_count]`.

**Auto-disable:** if `tenant_webhooks.consecutive_failures >= 40`, set `enabled=false` automatically and audit-log `webhook_auto_disabled`. Tenant must manually re-enable.

---

## HMAC Signing

```python
import hmac, hashlib, time

def sign_payload(secret_hex: str, raw_body: bytes) -> tuple[int, str]:
    t = int(time.time())
    msg = f"{t}.".encode() + raw_body
    sig = hmac.new(bytes.fromhex(secret_hex), msg, hashlib.sha256).hexdigest()
    return t, sig

# Header value: X-0Latency-Signature: t=1714000000,v1=abcdef...
```

Document this format in `docs/WEBHOOKS.md`.

---

## Test Plan

CC must produce **passing test execution evidence**, not collect-only counts.

### Unit tests (`tests/test_webhooks.py`)
- POST /webhooks tier gates: Free/Pro → 403, Scale → 201, Enterprise → 201
- POST /webhooks Scale tenant with existing active webhook → 409
- POST /webhooks Enterprise with 10 active webhooks → 409
- POST /webhooks invalid URL (http://, malformed) → 422
- GET /webhooks omits `secret` field, excludes soft-deleted
- POST /webhooks/{id}/rotate-secret on Scale tier → 403, on Enterprise → 200
- PATCH /webhooks/{id} cross-tenant → 404
- DELETE /webhooks/{id} sets `deleted_at`, row excluded from GET, in-flight deliveries continue
- HMAC signature verification roundtrip (sign → verify with secret → matches; sign → verify with wrong secret → fails)

### Integration tests (`tests/test_webhook_emission.py`)
- Supersession of synthesis row → row appears in webhook_deliveries
- Mock 200 response → status='delivered'
- Mock 500 response → status remains 'pending', next_attempt_at = now + 60s, consecutive_failures incremented
- 5 consecutive failures on one delivery → status='dead'
- 40 consecutive failures across deliveries → tenant_webhooks.enabled flips to false, audit event written
- Disabled webhook does not get rows enqueued
- Soft-deleted webhook does not get rows enqueued
- Rolled-back parent transaction → no webhook_deliveries row written (outbox correctness)

### Smoke test (after deploy)
- Create webhook pointing at webhook.site URL
- Trigger synthesis supersession on dogfood namespace
- Verify HTTP POST arrives within 60s with valid HMAC signature
- Verify webhook_deliveries row marked 'delivered'

**Mocking:** prefer `httpx.MockTransport` (no new dep). If respx is needed, `pip install respx --break-system-packages`. Document choice.

---

## File Manifest

New:
- `alembic/versions/028_*.py` (verify next sequence by `ls alembic/versions/ | sort | tail -3`)
- `api/webhooks.py` — endpoint handlers
- `api/webhook_emission.py` — enqueue helper + payload builder + HMAC signing
- `api/webhook_worker.py` — delivery loop, backoff
- `tests/test_webhooks.py`
- `tests/test_webhook_emission.py`
- `docs/WEBHOOKS.md` — public consumer documentation
- `docs/CP8-P5-4-COMPLETE.md` — deliverable summary
- `docs/CP8-P5-4-SCOPE.md` — this file

Modified:
- `api/main.py` — wire `/webhooks/*` router
- synthesis writer (CC locates) — call `enqueue_webhook_event` post-supersession
- Worker entry — register `process_webhook_queue` periodic job

DO NOT touch:
- `api/audit.py` (we're a producer, not consumer)
- existing migrations
- `0latency-mcp.service` config

---

## Out of Scope

- Per-webhook retry override (CP13)
- Webhook templates / payload customization (CP13)
- IP allowlist on destinations (CP14)
- Event types beyond `synthesis.replaced` (later)
- `/webhooks/deliveries` reader endpoint (P5.5 or CP13)
- Replay endpoint — defer

---

## Standing Rules

- `python3` not `python`
- `bash scripts/db_migrate.sh up`, NEVER direct `alembic upgrade head`
- Migration SQL must NOT contain inner `BEGIN/COMMIT`
- Use `_db_execute_rows`, not `_db_execute`
- `psycopg2` binds `list[str]` as `text[]`; for `uuid[]` use `%s::uuid[]`
- Broad `except Exception` must re-raise `NotImplementedError` first
- Test fixtures must set explicit values for feature-flag behavior
- File permissions: `chmod 644` files, `chmod 755` dirs after bulk writes
- Append-only audit semantics inviolable
- Paste-safe output only — never log secrets

---

## Halt Conditions

Halt and report back if:
- Migration 028 dry-run output does NOT end in `ROLLBACK`
- Test run finds existing tests broken (regression)
- Supersession code path is structurally different from scope (e.g., supersession in worker not API process)
- Anything beyond Tier 2 emerges (destructive op, refactor outside scope)

Otherwise execute fully autonomous, push branch, deliver completion doc, **DO NOT MERGE**.

---

## Branch + Commit

- Branch: `cp-p5-4-diff-webhooks`
- Commit format: `CP8 P5.4: <subscope>`
- Final commit: `CP8 P5.4: Diff webhooks complete`
- Push to origin, do not merge

---

## Definition of Done

1. Migration 028 applied to prod DB; alembic head advances
2. All 5 endpoints live behind tier gates, smoke-tested via curl
3. Worker delivers a real test webhook to webhook.site within 60s of supersession
4. HMAC signature verifies correctly with Python verifier sample in `docs/WEBHOOKS.md`
5. All new tests pass; no regression in existing 311 tests
6. `docs/CP8-P5-4-COMPLETE.md` delivered with: schema diff, endpoint list, smoke test evidence (HTTP codes only, NO secrets), DB row evidence
7. Branch pushed; deliverable summary back to operator
