# Security Policy — 0Latency

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly:

**Email:** security@0latency.ai  
**Response time:** We aim to acknowledge within 48 hours and provide a fix timeline within 7 days.

Please do **not** open public GitHub issues for security vulnerabilities.

---

## Security Architecture

### Authentication
- API keys are hashed with SHA-256 before storage — plaintext keys are never persisted
- Keys are validated with format checks (`zl_live_` prefix, 38-char length)
- Admin endpoints are restricted to localhost access only

### Tenant Isolation
- PostgreSQL Row-Level Security (RLS) enforced on all tenant-scoped tables
- RLS policies include both `USING` (read) and `WITH CHECK` (write) clauses
- Each API request sets `app.current_tenant_id` at the connection level
- Cross-tenant data access is impossible at the database layer

### Data Protection
- **In transit:** TLS 1.2+ enforced via Cloudflare (HSTS enabled, 1-year max-age)
- **At rest:** Database hosted on Supabase with encrypted storage volumes
- **Webhook secrets:** Stored as SHA-256 hashes, never in plaintext
- **API keys:** Stored as SHA-256 hashes, never in plaintext

### Input Validation
- All SQL queries use parameterized statements (psycopg2) — zero string interpolation
- All API inputs validated via Pydantic models with type, length, and range constraints
- Webhook URLs validated against SSRF attacks (private IP blocking, HTTPS-only, DNS rebinding protection)
- LLM extraction prompts use XML delimiters to prevent prompt injection from user content

### Security Headers
All API responses include:
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

### Rate Limiting
- Redis-backed, per-tenant rate limiting
- Free tier: 20 requests/minute
- Pro tier: 100 requests/minute
- Enterprise tier: 500 requests/minute

### Error Handling
- Client-facing errors return generic messages only
- Database errors and stack traces are logged server-side, never exposed to clients
- Request IDs included in all responses for debugging without information leakage

### Monitoring
- All requests logged with request ID, method, path, status, latency, and tenant ID
- Memory audit log tracks all create/update/delete operations with before/after state
- Webhook delivery attempts logged with status codes and response bodies

---

## Compliance Roadmap

| Standard | Status | Timeline |
|----------|--------|----------|
| Encrypted in transit | ✅ Complete | — |
| Encrypted at rest | ✅ Complete (Supabase) | — |
| Audit logging | ✅ Complete | — |
| Input validation | ✅ Complete | — |
| SSRF protection | ✅ Complete | — |
| CI/CD pipeline | ✅ Complete | — |
| SOC 2 Type II | 🔲 Planned | When enterprise demand warrants |
| HIPAA | 🔲 Planned | When healthcare use cases require |
| GDPR data deletion | 🔲 Planned | Pre-EU launch |

---

## Dependency Management

All Python dependencies are pinned to exact versions in `requirements.txt` to prevent supply chain attacks from unpinned upgrades. Dependencies are reviewed before version bumps.

---

*Last updated: 2026-03-21*
