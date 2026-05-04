
## Phase 3 — Multi-Agent Consensus Operational Shape

**Trigger:** synthesize_cluster() dispatcher in src/synthesis/tier_gates.py. Routes to consensus path on Enterprise tier; single-agent path on Scale/Pro tiers.

**Per consensus run, expected events:**
1. consensus_run_started (1x)
2. synthesis_candidate_prepared (Nx, one per successful candidate)
3. synthesis_written (1x — the merged consensus row)
4. consensus_disagreement_logged (0 or 1x — only if rejected claims exist)

**Skip/failure events:**
- consensus_skipped_insufficient_agents — <2 distinct agent_ids in cluster
- consensus_failed_insufficient_candidates — <2 candidates succeeded

**Disagreement queries:**

Recent unresolved disagreements:
SELECT id, cluster_id, candidate_count, detected_at
FROM memory_service.synthesis_disagreements
WHERE tenant_id = '<tenant>' AND resolution IS NULL
ORDER BY detected_at DESC LIMIT 50;

Consensus runs in last 24h:
SELECT m.id, m.created_at, m.contributing_agents
FROM memory_service.memories m
WHERE m.tenant_id = '<tenant>'
AND m.memory_type = 'synthesis'
AND m.consensus_method = 'majority_vote'
AND m.created_at > now() - interval '24 hours'
ORDER BY m.created_at DESC;

**Manual rerun:**
python3 -c "import os, psycopg2; from src.synthesis.tier_gates import synthesize_cluster; conn = psycopg2.connect(os.environ['DATABASE_URL']); print(synthesize_cluster(tenant_id='<tenant>', cluster_id='<cluster>', cluster_memory_ids=[<uuids>], role_tag='public', db_conn=conn)); conn.commit()"
