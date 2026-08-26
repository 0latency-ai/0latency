# agent_config — prepared change and rollback record

**Date:** 2026-08-26
**Box:** 164.90.156.169 · `/root/.openclaw/workspace/memory-product`
**Status:** **PREPARED, NOT APPLIED.** Nothing in this document is live.
`memory_service.agent_config` holds its original 3 rows.

---

## 1. Current state — unchanged

```
agent_id | tenant_id                            | rec  | sem | imp  | acc | half_life
default  | 00000000-0000-0000-0000-000000000000 | 0.35 | 0.4 | 0.15 | 0.1 | 14
echo     | 00000000-0000-0000-0000-000000000000 | 0.35 | 0.4 | 0.15 | 0.1 | 3
thomas   | 00000000-0000-0000-0000-000000000000 | 0.35 | 0.4 | 0.15 | 0.1 | 3
```

There is **no `id` column**. Row identity is the composite `(agent_id, tenant_id)`,
which is also why the primary key needs widening before per-tenant rows can exist
at all — see `alembic/versions/b4c1d2e3f5a6_widen_agent_config_pk.py`, written and
dry-run but not applied.

## 2. The prepared change

```sql
INSERT INTO memory_service.agent_config
  (agent_id, tenant_id, context_budget, recency_weight, semantic_weight,
   importance_weight, access_weight, recency_half_life_days)
VALUES ('user-justin', '44c3080d-c196-407d-a606-4ea9f62ba0fc'::uuid,
        4000, 0.10, 0.65, 0.15, 0.10, 3);
```

Rollback, should it ever be applied:

```sql
DELETE FROM memory_service.agent_config
WHERE agent_id = 'user-justin'
  AND tenant_id = '44c3080d-c196-407d-a606-4ea9f62ba0fc'::uuid;
```

Identity pair: **`('user-justin', '44c3080d-c196-407d-a606-4ea9f62ba0fc')`**.

## 3. Measured result while it was briefly live

Applied 2026-08-26 05:0x UTC, measured, then deleted (`DELETE 1`) the same session.
Sub-day bucket was 153 rows at both measurements, so the deltas below are not
ingestion drift.

| | before | after |
|---|---|---|
| gate counts, six queries | 155,159,161,147,163,157 | 50,69,37,49,54,42 |
| union / intersection | 176 / 141 | 80 / **25** |
| q1 rows under 1 day | 136 of 155 (88%) | **0 of 50** |
| union rows ≥30 days reached | **3** | **77** |
| thomas_eval | 1/10 | 1/10 |
| query-independent ceiling | 0.600 vs 0.400 gate — FAIL | **0.350 — PASS** |

The projection made before applying — `[50,69,37,49,54,42] inter=25 old=77` —
reproduced row for row.

## 4. Why it is not applied

`agent_config` is read by **both** scorers. The measured gain is entirely on
`recall_cross_agent`, and that scorer serves no production traffic: of 3,725
`POST /recall` calls in the seven days to 2026-08-26, **4** reached it, all four
inside a two-minute window on 2026-08-25 during the analysis session that
produced `RECENCY-WEIGHTING-ANALYSIS.md`. Every production surface — the live MCP
server (`server-sse.js:173`), the shipped MCP npm package, the Chrome extension,
and `thomas_eval.py` itself — omits `cross_agent`, and `api/main.py:599` defaults
it `False`.

Applying this would change shared configuration for 100% of recall traffic to fix
a path serving 0% of it, justified by a ten-question eval that was itself
mis-scoring at the time (see `f061b6b`). Decision on 2026-08-26: do not apply.

## 5. Related, also not applied

- `b4c1d2e3f5a6` — widens the primary key to `(agent_id, tenant_id)` and
  replicates the `default` row to all 17 tenants that currently reach it through
  the cross-tenant bleed. Dry-run clean, round-trips clean, **not applied**.
- The `_load_agent_config` tenant predicate. Must not land before
  `b4c1d2e3f5a6`, or 16 tenants silently drop from half-life 14 to the code
  fallback of 3.
