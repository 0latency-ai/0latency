# API Endpoints

Auto-generated inventory of all REST endpoints in the Zero Latency Memory API.

## Memory Writes

| Method | Path | Function | Auth Required | Purpose |
|--------|------|----------|---------------|---------|
| POST | /extract | extract_endpoint | Yes | Extract memories from a conversation turn. |
| POST | /memories/seed | seed_endpoint | Yes | Seed memories directly from raw facts, bypassing the extraction pipeline. |
| POST | /memories/extract | async_extract_endpoint | Yes | Async memory extraction. Accepts instantly (202), processes in background. |
| POST | /memories/checkpoint | create_checkpoint | Yes | CP7b Phase 2: Mid-thread rollup checkpoint creation. |
| POST | /memories/resume | create_resume_checkpoint | Yes | CP7b Phase 4: Auto-resume meta-summary endpoint |
| POST | /extract/batch | batch_extract | Yes | Extract memories from multiple conversation turns in one request. |
| POST | /memories/import | bulk_import_endpoint | Yes | Bulk import: accepts a large text document, chunks it, extracts memories from each chunk. |
| POST | /memories/import-thread | thread_import_endpoint | Yes | Thread import: accepts a conversation export and extracts memories from each turn pair. |
| POST | /feedback | feedback_endpoint | Yes | Submit feedback on recalled memories. |
| POST | /webhooks | create_webhook_endpoint | Yes | Register a webhook for memory events. |
| POST | /criteria | create_criteria_endpoint | Yes | Create a custom recall scoring criteria. |
| POST | /schemas | create_schema_endpoint | Yes | Create a custom extraction schema. |
| POST | /org/memories | store_org_memory_endpoint | Yes | Store an organization-level shared memory. |
| POST | /memories/{memory_id}/promote | promote_to_org_endpoint | Yes | Promote an agent memory to organization level. |
| POST | /memories/batch-delete | batch_delete_endpoint | Yes | Delete multiple memories in one request. |
| POST | /memories/batch-search | batch_search_endpoint | Yes | Search with multiple queries in one request. |
| POST | /demo/extract | demo_extract_endpoint | No | Public demo endpoint — extracts memories from text without authentication. |

## Memory Reads

| Method | Path | Function | Auth Required | Purpose |
|--------|------|----------|---------------|---------|
| POST | /recall | recall_endpoint | Yes | Recall relevant memories for a conversation context. |
| GET | /memories | list_memories | No | List memories for authenticated tenant. |
| GET | /memories/search | search_memories | No | Search memories by query. |
| GET | /memories/export | export_memories | No | Export all memories for a tenant. |
| GET | /memories/extract/{job_id} | get_extract_job | Yes | Check status of an async extraction job. |
| GET | /memories/{memory_id}/history | memory_history_endpoint | Yes | Get version history for a specific memory. |
| GET | /webhooks | list_webhooks_endpoint | Yes | List all webhooks for the current tenant. |
| GET | /criteria | list_criteria_endpoint | No | List all recall criteria for tenant. |
| GET | /schemas | list_schemas_endpoint | Yes | List all schemas for the current tenant. |
| GET | /org/memories | list_org_memories_endpoint | No | List organization-level memories. |
| GET | /org/memories/recall | recall_org_memories_endpoint | No | Recall organization-level memories. |
| GET | /tenant-info | get_tenant_info | Yes | Get current tenant information. |
| GET | /agents | list_agents | Yes | List all distinct agent_id values for the authenticated tenant with memory counts. |
| GET | /usage | get_usage | No | Get API usage statistics for tenant. |

## Graph Queries

| Method | Path | Function | Auth Required | Purpose |
|--------|------|----------|---------------|---------|
| GET | /graph/entity | graph_entity_endpoint | No | Get entity subgraph with relationships. |
| GET | /graph/entities | graph_entities_endpoint | No | List all entities for tenant/agent. |
| GET | /graph/entity/memories | graph_entity_memories_endpoint | No | Get memories associated with an entity. |
| GET | /graph/path | graph_path_endpoint | No | Find path between two entities in the knowledge graph. |

## Updates & Deletes

| Method | Path | Function | Auth Required | Purpose |
|--------|------|----------|---------------|---------|
| PUT | /memories/{memory_id} | update_memory_endpoint | Yes | Update an existing memory. |
| DELETE | /memories/{memory_id} | delete_memory | Yes | Delete a specific memory. Tenant-isolated. |
| DELETE | /webhooks/{webhook_id} | delete_webhook_endpoint | Yes | Delete a webhook. |
| DELETE | /criteria/{criteria_id} | delete_criteria_endpoint | Yes | Delete a criteria. |
| DELETE | /schemas/{schema_id} | delete_schema_endpoint | Yes | Delete a schema. |
| DELETE | /org/memories/{memory_id} | delete_org_memory_endpoint | Yes | Delete an org memory. |

## Admin & Tenant Management

| Method | Path | Function | Auth Required | Purpose |
|--------|------|----------|---------------|---------|
| POST | /api-keys | create_api_key | No | Create a new tenant and API key. Requires admin authentication. |
| POST | /admin/rotate-key/{tenant_id} | rotate_api_key | No | Rotate API key for a tenant. Old key is immediately invalidated. |
| POST | /admin/revoke-key/{tenant_id} | revoke_api_key | No | Revoke API key by deactivating tenant. Immediate effect. |
| POST | /admin/reactivate/{tenant_id} | reactivate_tenant | No | Reactivate a previously revoked tenant. |
| GET | /admin/tenants | list_tenants | No | List all tenants. Admin only. |
| DELETE | /admin/delete-user/{email} | admin_delete_user | No | ADMIN: Delete user by email |
| POST | /admin/fix-github-tenant | fix_github_tenant | No | ADMIN: Generate API key for GitHub tenant |

## Health & Monitoring

| Method | Path | Function | Auth Required | Purpose |
|--------|------|----------|---------------|---------|
| GET | /dashboard | dashboard | Yes | Tenant dashboard UI (requires API key). |
| GET | /metrics | metrics_endpoint | No | Performance metrics — no auth required. Shows request rates, latency percentiles, error rates. |
| GET | /observability/anomalies | anomalies_endpoint | No | Get recent anomaly detection results. |
| GET | /observability/anomalies/summary | anomalies_summary_endpoint | No | Summary of recent anomaly detection activity. Public endpoint. |
| GET | /observability/errors/stats | error_stats_endpoint | No | Error statistics for monitoring. Public endpoint. |

---

**Total Endpoints:** 54  
**Last Updated:** Auto-generated from api/main.py
