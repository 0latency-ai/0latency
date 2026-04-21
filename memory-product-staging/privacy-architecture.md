# Privacy Architecture — Agent Memory Service

**Date:** March 18, 2026
**Status:** Draft

---

## 1. Why Privacy Is Load-Bearing

An agent memory service stores the most sensitive data possible: structured facts about people's lives, decisions, preferences, relationships, work details, and behavioral patterns. A breach or mishandling isn't just a PR problem — it's a trust-destroying event that kills adoption.

Privacy must be designed into the architecture from day one, not bolted on.

---

## 2. Deployment Models & Privacy Implications

### Self-Hosted (Free Tier)
- **Data location:** User's own infrastructure
- **Our access:** Zero. We never see the data.
- **Privacy burden:** Entirely on the user
- **Compliance:** User's responsibility
- **This is the easiest privacy story.** "Your data never leaves your machine."

### Hosted (Paid Tiers)
- **Data location:** Our managed infrastructure (Supabase/Postgres on cloud provider)
- **Our access:** Technically possible (we manage the database)
- **Privacy burden:** On us
- **Compliance:** GDPR, CCPA, potentially SOC 2 for enterprise
- **This is where all the hard work lives.**

---

## 3. Privacy Principles

### Principle 1: Minimum Data, Maximum Isolation
- Each user/agent gets its own schema or row-level security (RLS) namespace
- No shared tables where User A's memories could leak to User B
- Supabase RLS makes this straightforward with proper policies
- Queries are always scoped to the authenticated agent_id

### Principle 2: Encryption at Rest and in Transit
- **In transit:** TLS 1.3 for all API communication (standard, non-negotiable)
- **At rest:** Supabase encrypts at rest by default (AES-256)
- **Application-level encryption (optional):** User can provide an encryption key; memories are encrypted before storage. We can't read them even with database access. Trade-off: breaks server-side semantic search (embeddings can't be encrypted meaningfully)
- **Recommendation:** Offer application-level encryption as an option for paranoid users, with the caveat that it disables server-side recall optimization. Most users will prefer the functional version.

### Principle 3: User Owns Their Data
- **Export:** Users can export all their memories at any time (JSON, CSV)
- **Delete:** Users can delete individual memories, all memories, or their entire account
- **Deletion is real:** Not soft-delete. When a user says delete, the data is gone. Backups rotate out within 30 days.
- **Portability:** Export format is documented and open. Users can migrate from hosted to self-hosted (or vice versa) at any time.

### Principle 4: No Training on User Data
- **Explicit policy:** We never use stored memories to train models, improve our service, or for any purpose other than serving that specific user's agent.
- **This is non-negotiable.** It's in the ToS, the privacy policy, and the marketing.
- The extraction model (Gemini Flash, etc.) processes conversation turns but doesn't retain them — standard API usage with no training.

### Principle 5: Transparency
- **Audit log:** Every read and write to the memory system is logged
- **Memory dashboard:** Users can see exactly what their agent "knows" — every stored memory, with source reference, confidence score, and last accessed timestamp
- **No hidden memories:** The agent can't store things the user can't see

---

## 4. Compliance Requirements

### GDPR (EU Users)
| Requirement | Implementation |
|-------------|----------------|
| Right to access | Export endpoint — user can download all data |
| Right to rectification | Edit endpoint — user can correct any memory |
| Right to erasure | Delete endpoint — hard delete with backup rotation |
| Data portability | Open JSON export format |
| Lawful basis | Consent (user explicitly creates account and stores memories) |
| Data Processing Agreement | Required for hosted tier — template DPA available |
| Data location | Option to specify EU-only hosting (Supabase supports EU regions) |

### CCPA (California Users)
| Requirement | Implementation |
|-------------|----------------|
| Right to know | Dashboard shows all stored data |
| Right to delete | Delete endpoint |
| Right to opt-out of sale | We don't sell data. Period. |
| Non-discrimination | No service degradation for exercising rights |

### SOC 2 (Enterprise)
- Not needed at launch
- Required if we pursue enterprise tier ($49+/mo)
- Supabase is SOC 2 Type II certified — we inherit some compliance
- Full SOC 2 for our layer would require ~$20-50K and 3-6 months
- **Decision:** Defer until enterprise revenue justifies it

---

## 5. Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| Database breach (attacker gets DB access) | Critical | Encryption at rest, RLS isolation, optional app-level encryption |
| API key leak (user's key exposed) | High | Key rotation, rate limiting, IP allowlisting option |
| Insider threat (we access user data) | Medium | Audit logs, principle of least privilege, no production DB access without logged justification |
| Extraction model leaks (API provider trains on data) | Medium | Use API providers with explicit no-training policies (Anthropic, Google Cloud). Document in privacy policy. |
| Cross-tenant data leak (bug exposes wrong user's data) | High | RLS, integration tests that verify isolation, separate schemas for enterprise |
| Memory poisoning (attacker injects false memories) | Medium | Confidence scoring, source attribution, user can review/delete any memory |

---

## 6. Technical Implementation

### Authentication
- API key per agent (generated on account creation)
- Optional: OAuth2 for enterprise SSO
- All requests authenticated — no anonymous access to memory endpoints

### Row-Level Security (Postgres/Supabase)
```sql
-- Every query automatically filtered to the authenticated agent
CREATE POLICY "agent_isolation" ON memories
  USING (agent_id = current_setting('app.current_agent_id'));

-- Same for all tables
CREATE POLICY "agent_isolation_edges" ON memory_edges
  USING (
    source_id IN (SELECT id FROM memories WHERE agent_id = current_setting('app.current_agent_id'))
  );
```

### Deletion Pipeline
```
User requests deletion
  → Immediate: soft-delete (removed from queries, marked for hard delete)
  → Within 1 hour: hard delete from primary database
  → Within 24 hours: removed from vector index
  → Within 30 days: rotated out of backups
  → Confirmation sent to user
```

### Data Retention Defaults
| Data Type | Default Retention | User Override |
|-----------|-------------------|---------------|
| Active memories | Indefinite (until deleted or decayed to archive) | Can set max retention period |
| Archived memories (decayed) | 90 days | Can extend or delete |
| Audit logs | 30 days | Can request export before deletion |
| Session handoffs | 30 days | Can extend |

---

## 7. Privacy in Marketing

Privacy is a feature, not a checkbox. For our target audience (developers, technical users, people running persistent AI agents), privacy is a buying decision factor.

**Key messages:**
- "Your memories, your data. Self-host for free, or let us host with full encryption."
- "We never train on your data. Ever."
- "See everything your agent knows. Delete anything, anytime."
- "GDPR and CCPA compliant from day one."

**Trust signals:**
- Open-source self-hosted option (you can audit the code)
- Public privacy policy written in plain English
- Dashboard showing exactly what's stored
- Export/delete always available

---

## 8. Open Questions

| # | Question | Current Thinking | Decision Needed By |
|---|----------|-----------------|-------------------|
| 1 | App-level encryption vs. DB-level only? | Offer as option; most users won't need it | Phase 2 |
| 2 | EU hosting required at launch? | No — add when we have EU users asking | Phase 8 |
| 3 | SOC 2 certification timeline? | Defer until enterprise revenue | Post-launch |
| 4 | What if an extraction model provider changes their training policy? | Monitor; switchable models by design | Ongoing |
| 5 | Should we log what memories were injected into context (for user audit)? | Yes — adds transparency, minimal cost | Phase 3 |

---

*Last updated: March 18, 2026*
