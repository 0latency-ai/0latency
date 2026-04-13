# 0Latency Site Audit — March 30, 2026

## Summary
- **Total pages audited:** 27
- **All pages returned 200 ✅**
- **Broken links found:** 10 (real issues — excluding Cloudflare email obfuscation false positives)
- **Design issues found:** 12
- **Content issues found:** 5

---

## Broken Links

> **Note:** All `cdn-cgi/l/email-protection` links are Cloudflare's email obfuscation — they return 404 when curl'd directly but work fine in-browser. These are **false positives** and excluded below.

| Page | Broken Link | Status | Severity |
|------|------------|--------|----------|
| Homepage | `https://api.0latency.ai` | 404 | **High** — linked as API base URL |
| Homepage | `https://api.0latency.ai/health` | 405 | **High** — health endpoint returns Method Not Allowed |
| Homepage | `https://www.npmjs.com/package/@0latency/mcp-server` | 403 | **Medium** — npm package not public or doesn't exist |
| Docs | `https://docs.0latency.ai/api-reference` | 403/timeout | **High** — docs subdomain not serving content |
| Billing | `tier.slice(1)}` in href | Malformed | **High** — JavaScript template literal leaked into HTML href |
| Integrations/MCP | `https://github.com/0latency/mcp-server` | 404 | **High** — GitHub repo doesn't exist (try `0latency-ai/mcp-server`?) |
| Login | `https://api.0latency.ai/auth/github` | 405 | **Medium** — OAuth endpoint returning 405 |
| Login | `https://api.0latency.ai/auth/google` | 405 | **Medium** — OAuth endpoint returning 405 |
| Homepage | `https://fonts.googleapis.com` (bare domain) | 404 | **Low** — likely a preconnect hint, not a navigable link |
| Homepage | `https://fonts.gstatic.com` (bare domain) | 404 | **Low** — same as above, preconnect |
| Integrations/Claude Web | `https://claude.ai` | 403 | **Low** — Anthropic blocks curl; works in browser |

---

## Design Issues

| Page | Issue | Severity |
|------|-------|----------|
| Blog index (`/blog/`) | `background: #000` (black) on line 16 | **High** — violates light theme requirement |
| Blog index (`/blog/`) | No `<nav>` element in header | **Medium** — inconsistent with other pages |
| `claude-desktop.html` | Missing `<footer>`, missing logo, no `<header>` tag | **High** — incomplete page template |
| `claude-code.html` | Missing `<footer>`, missing logo, no `<header>` tag | **High** — incomplete page template |
| `claude-web.html` | Missing `<footer>`, missing logo, no `<header>` tag | **High** — incomplete page template |
| `cursor.html` | Missing `<footer>`, missing logo, no `<header>` tag | **High** — incomplete page template |
| `windsurf.html` | Missing `<footer>`, missing logo, no `<header>` tag | **High** — incomplete page template |
| `mcp.html` | No `<header>` tag (has nav) | **Medium** — inconsistent structure |
| `login.html` | No `<header>`, no `<nav>`, no `<footer>` | **High** — standalone page, no site chrome |
| `case-study-thomas.html` | No `<header>` tag (has nav) | **Low** — semantic only |
| `privacy.html`, `roadmap.html`, `security.html` | No `<header>` tag (have nav) | **Low** — semantic, functionally fine |
| Billing page | Green (#16a34a) and red (#fef2f2) status backgrounds | **Low** — acceptable for status indicators |

---

## Content Issues

| Page | Issue |
|------|-------|
| `/docs/` | Missing `<meta name="description">` |
| `/billing.html` | Missing `<meta name="description">` |
| `/chrome-extension.html` | Missing `<meta name="description">` |
| `/login.html` | Missing `<meta name="description">` |
| `/blog/` (index) | Missing `<meta name="description">` |

**No placeholder text (Lorem ipsum/TODO) found on any page. ✅**
**Logo assets (`/logos/0latency-logo-complete.svg` and `/logos/0latency-icon-32.png`) both return 200. ✅**
**No atom-one-dark or dark code themes found. ✅**

---

## Consistency Audit

| Check | Result |
|-------|--------|
| Same header across all pages? | **❌ No** — 5 integration pages (claude-desktop, claude-code, claude-web, cursor, windsurf) + login missing standard header |
| Same footer across all pages? | **❌ No** — Same 5 integration pages + login missing footer |
| Same CSS variables? | **⚠️ Mostly** — blog index uses inline styles with `#000` instead of CSS vars |
| Nav links consistent? | **⚠️ Mostly** — blog index has different nav structure |
| Orange accent (#f97316)? | **✅ Yes** — used consistently across main pages |

---

## Pages Passing All Checks
- `https://0latency.ai/case-study-thomas.html` ✅
- `https://0latency.ai/integrations/` ✅
- `https://0latency.ai/integrations/langchain.html` ✅
- `https://0latency.ai/integrations/crewai.html` ✅
- `https://0latency.ai/integrations/autogen.html` ✅
- `https://0latency.ai/integrations/openclaw.html` ✅
- `https://0latency.ai/privacy.html` ✅
- `https://0latency.ai/terms.html` ✅
- `https://0latency.ai/security.html` ✅
- `https://0latency.ai/support.html` ✅
- `https://0latency.ai/roadmap.html` ✅
- `https://0latency.ai/blog/why-your-agent-forgets.html` ✅
- `https://0latency.ai/blog/mem0-vs-0latency.html` ✅
- `https://0latency.ai/blog/memory-layer-93-cents.html` ✅

---

## Recommendations (Priority Order)

### 🔴 Critical (Fix Before Launch)

1. **Fix billing.html template literal leak** — `tier.slice(1)}` is rendering as a literal href. The JavaScript template isn't being interpolated. This is a broken page for users trying to manage billing.

2. **Fix 5 integration pages missing header/footer** — `claude-desktop`, `claude-code`, `claude-web`, `cursor`, `windsurf` are all missing the standard site chrome (header with logo, footer). These look like they were built from a different/older template. Apply the shared header/footer component.

3. **Fix GitHub MCP repo link** — `https://github.com/0latency/mcp-server` returns 404. Either create the repo, change the org to `0latency-ai`, or remove the link.

4. **Fix docs.0latency.ai** — Subdomain returns 403. Either deploy docs or remove the link from the docs page.

### 🟡 Important

5. **Fix blog index dark background** — Line 16 has `background: #000`. Change to `#ffffff` or `#f9fafb` to match the light theme across the rest of the site.

6. **Add login.html site chrome** — Currently a standalone page with no header, nav, or footer. Add standard components for brand consistency.

7. **Add meta descriptions** to `/docs/`, `/billing.html`, `/chrome-extension.html`, `/login.html`, `/blog/` — important for SEO.

8. **Verify API endpoints** — `api.0latency.ai` base URL returns 404, health returns 405, auth endpoints return 405. Confirm these are expected (API may only respond to POST/specific methods) or fix.

### 🟢 Nice to Have

9. **Standardize header markup** — Some pages use `<header>` + `<nav>`, some use just `<nav>`. Standardize to `<header><nav>...</nav></header>` for accessibility and consistency.

10. **npm package visibility** — `@0latency/mcp-server` returns 403. If published, ensure it's public. If not yet published, remove or mark as "coming soon."

---

## Design Aesthetic vs. Rasmic Reference

Comparing to [rasmic.xyz](https://www.rasmic.xyz/) (clean, minimal, light theme):

| Aspect | Rasmic Standard | 0Latency Status |
|--------|----------------|-----------------|
| Light backgrounds | White/near-white everywhere | ✅ Mostly — except blog index (#000) |
| Clean typography | Dark text on light | ✅ Good across main pages |
| Minimal chrome | Simple nav, clean footer | ⚠️ Inconsistent — 6 pages missing footer |
| Professional feel | Consistent spacing/layout | ⚠️ Integration sub-pages feel rushed |
| Orange accent | N/A (Rasmic uses blue) | ✅ #f97316 used well |
| Code blocks | Light theme | ✅ No dark themes found |

**Overall:** The main pages (homepage, pricing, docs, integrations index, blog posts) look solid. The gaps are in the "second tier" pages — newer integration guides and the billing/login pages that need the shared template applied.
