# Synthesis Policy DSL

The Synthesis Policy DSL is a JSON-based configuration language that controls how the 0Latency memory service synthesizes, cascades, and manages memory artifacts. Each tenant has a single `synthesis_policy` JSONB column that governs all synthesis behavior.

## Policy Structure

A synthesis policy contains four top-level sections:

```json
{
  "redaction_rules": { ... },
  "role_visibility": { ... },
  "retention": { ... },
  "consensus_requirements": { ... }
}
```

### 1. Redaction Rules

Controls how synthesis nodes react when their source memories are redacted or modified.

```json
"redaction_rules": {
  "on_source_redacted": "resynthesize_without" | "invalidate" | "mark_pending_review",
  "on_source_modified": "resynthesize_without" | "invalidate" | "mark_pending_review",
  "cascade_depth": "evidence_chain_only" | "full_cluster"
}
```

**Fields:**
- `on_source_redacted`: Action when a source memory is redacted
  - `invalidate`: Mark synthesis as invalid immediately
  - `resynthesize_without`: Automatically regenerate without the redacted source
  - `mark_pending_review`: Flag for manual review
- `on_source_modified`: Action when a source memory is modified
  - Same options as `on_source_redacted`
- `cascade_depth`: How far to propagate redaction/modification events
  - `evidence_chain_only`: Only direct dependencies
  - `full_cluster`: All transitively connected synthesis nodes

**Phase 2-5 integration:** These rules control the redaction cascade state machine shipped in CP8 Phase 5.

### 2. Role Visibility

Controls which tenant roles can see synthesis outputs and cross-role read access.

```json
"role_visibility": {
  "default_role": "public" | "engineering" | "product" | "revenue" | "legal",
  "produce_for_roles": ["public", "engineering", ...],
  "cross_role_read": false
}
```

**Fields:**
- `default_role`: Default role for new synthesis artifacts
- `produce_for_roles`: List of roles that synthesis should generate artifacts for (non-empty array)
- `cross_role_read`: Whether users can read artifacts from other roles

**Valid roles:** `public`, `engineering`, `product`, `revenue`, `legal`

**Phase 2-5 integration:** Role-based synthesis and filtering logic shipped in CP8 Phase 3.

### 3. Retention

Controls archival and expiration of synthesis artifacts.

```json
"retention": {
  "max_age_days": null | <integer ≥ 1>,
  "auto_archive": false
}
```

**Fields:**
- `max_age_days`: Maximum age before archival (null = no limit)
- `auto_archive`: Whether to automatically archive old synthesis artifacts

**Phase 2-5 integration:** Retention enforcement shipped in CP8 Phase 4.

### 4. Consensus Requirements

Configures multi-agent synthesis and consensus mechanisms.

```json
"consensus_requirements": {
  "method": "single_agent" | "majority_vote" | "weighted" | "unanimous",
  "min_agents": 1-10,
  "tie_breaker": "highest_confidence" | "most_recent" | "most_sources"
}
```

**Fields:**
- `method`: Consensus algorithm
  - `single_agent`: No consensus, single synthesis
  - `majority_vote`: Simple majority
  - `weighted`: Weighted by confidence scores
  - `unanimous`: All agents must agree
- `min_agents`: Minimum number of agents for consensus (1-10)
- `tie_breaker`: How to resolve ties in voting

**Phase 2-5 integration:** Consensus synthesis shipped in CP8 Phase 2.

## Default Policies by Tier

### Free/Pro/Scale (Standard)

```json
{
  "redaction_rules": {
    "on_source_redacted": "resynthesize_without",
    "on_source_modified": "mark_pending_review",
    "cascade_depth": "evidence_chain_only"
  },
  "role_visibility": {
    "default_role": "public",
    "produce_for_roles": ["public"],
    "cross_role_read": false
  },
  "retention": {
    "max_age_days": null,
    "auto_archive": false
  },
  "consensus_requirements": {
    "method": "majority_vote",
    "min_agents": 1,
    "tie_breaker": "highest_confidence"
  }
}
```

### Enterprise

Same as standard, except:
- `role_visibility.produce_for_roles`: `["public", "engineering", "product", "revenue", "legal"]`
- `consensus_requirements.min_agents`: `3`

## Usage Examples

### Reading Current Policy

```python
import psycopg2
from src.synthesis.policy import load_policy

conn = psycopg2.connect(DATABASE_URL)
tenant_id = "your-tenant-uuid"

policy = load_policy(tenant_id, conn)
print(policy["consensus_requirements"]["min_agents"])
```

### Updating a Single Field

```python
from src.synthesis.policy import load_policy, save_policy

conn = psycopg2.connect(DATABASE_URL)
tenant_id = "your-tenant-uuid"

# Load current policy
policy = load_policy(tenant_id, conn)

# Modify retention
policy["retention"]["max_age_days"] = 365
policy["retention"]["auto_archive"] = True

# Validate and save
save_policy(tenant_id, policy, conn)
conn.commit()
```

### Bulk Compliance Update

```python
import psycopg2
from src.synthesis.policy import load_policy, save_policy

conn = psycopg2.connect(DATABASE_URL)

# Get all enterprise tenants
with conn.cursor() as cur:
    cur.execute("SELECT id FROM memory_service.tenants WHERE plan = 'enterprise'")
    enterprise_tenants = [row[0] for row in cur.fetchall()]

# Update all to require unanimous consensus for legal compliance
for tenant_id in enterprise_tenants:
    policy = load_policy(tenant_id, conn)
    policy["consensus_requirements"]["method"] = "unanimous"
    policy["consensus_requirements"]["min_agents"] = 3
    save_policy(tenant_id, policy, conn)

conn.commit()
```

### Validating a Policy Before Use

```python
from src.synthesis.policy import validate_policy

my_policy = {
    "redaction_rules": { ... },
    "role_visibility": { ... },
    "retention": { ... },
    "consensus_requirements": { ... }
}

is_valid, errors = validate_policy(my_policy)
if not is_valid:
    print(f"Policy validation failed: {errors}")
```

## Schema Enforcement

All policies are validated against a JSON Schema before being saved to the database. Invalid policies will raise a `ValueError`.

The schema is defined in `src/synthesis/policy.py` as `POLICY_JSON_SCHEMA`.

## Forward References

- **Phase 2:** Consensus synthesis engine reads `consensus_requirements`
- **Phase 3:** Role-based synthesis and filtering reads `role_visibility`
- **Phase 4:** Retention enforcement cron reads `retention`
- **Phase 5:** Redaction cascade state machine reads `redaction_rules`
