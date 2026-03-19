# Colorado Expanded Contacts — Summary

**Date:** 2026-03-11
**Researcher:** Reed (subagent)
**Existing base:** 236 verified public school district contacts (not duplicated)

## Counts by Category

| Category | Contacts | With Name | With Email | With Phone |
|----------|----------|-----------|------------|------------|
| BOCES | 10 | 0 | 0 | 0 |
| Charter | 7 | 1 | 2 | 6 |
| Private (ACIS HS-level) | 19 | 3 | 2 | 4 |
| Tribal | 2 | 0 | 0 | 1 |
| Umbrella Orgs | 2 | 1 | 1 | 1 |
| **Total** | **40** | **5** | **5** | **12** |

## High-Value Targets (Prioritized)

### Tier 1 — Multiplier Contacts
1. **ACIS (Alan Smiley, Exec Dir)** — Represents 39 independent schools. One relationship = access to all member heads of school. Phone: 303-444-2201.
2. **CO League of Charter Schools** — Umbrella for charter sector. Email: info@coloradoleague.org.

### Tier 2 — Named Decision-Makers
3. **Colorado Academy** — Dr. Mike Davis (Head of School), Christina Garza (Upper School Head). Confirmed email pattern: firstname.lastname@coloradoacademy.org. PreK-12.
4. **Kent Denver School** — David Braemer (Head of School). 303-770-7660. Grades 6-12, Englewood.
5. **Fountain Valley School** — Megan Harlan (Head of School). 719-390-7035. Grades 9-12 boarding/day, Colorado Springs.
6. **Animas High School** — Rebecca Ruland (Head of School). 970-247-2474. Charter HS, Durango.

### Tier 3 — Org-Level Contacts (Need Names)
7. KIPP Colorado — info@kippcolorado.org, 303-934-3245
8. DSST Public Schools — 303-524-6324
9. James Irwin Charter Schools — 719-302-9000
10. SkyView Academy — 303-471-8439
11. The STEAD School — 720-835-2995

## Method Notes

### What Worked
- **ACIS directory** (acischools.org/schools) was the single best source — complete list of 39 ACIS-accredited independent schools with grades, locations, and school types
- Direct website fetches for charter schools (Animas HS, STEAD, KIPP, etc.)
- Fountain Valley School (fvs.edu) — clean Blackbaud site with full leadership and contact info

### What Didn't Work
- **BOCES websites** were almost universally blocked — most use edliocloud.com hosting behind Cloudflare, DNS failures, or empty JS-rendered pages. This was the biggest gap.
- **CDE BOCES directory** was also inaccessible
- **coloradoboces.org** member directory links were broken (404s)
- Many private school leadership pages use Blackbaud hosting and return 404s for direct URL guesses
- Email addresses on charter school sites were mostly obscured by Cloudflare email protection (`/cdn-cgi/l/email-protection`)

### Recommendations for Thomas
1. **BOCES gap is critical.** Consider:
   - Using browser automation (not web_fetch) to render JS-heavy BOCES sites
   - Calling CDE directly: 303-866-6600 to request BOCES executive director list
   - Checking if CDE publishes a downloadable directory (PDF or Excel)
   - LinkedIn searches for "[BOCES name] executive director Colorado"
2. **ACIS is the play for private schools.** Contact Alan Smiley directly — he can intro to all 39 member heads of school. One warm intro = 15+ HS-level schools reached.
3. **Email enrichment needed.** Most contacts have phone but not email. ZeroBounce the guessed emails in the JSON. For others, LinkedIn or direct calls will be needed.
4. **Charter school contacts** mostly have org-level phones. Individual names can be found via LinkedIn or by calling directly.
5. **Tribal contacts** — Southern Ute education dept phone is 970-563-0237 (from earlier fetch, needs verification). Ute Mountain Ute needs a direct call to main tribal number.

### ACIS Member Schools with High School Programs
These are the highest-value private school targets (financial literacy is HS-level):

| School | Location | Grades | Type |
|--------|----------|--------|------|
| Colorado Academy | Denver | PreK-12 | Day |
| Colorado Rocky Mountain School | Carbondale | 9-12 | Boarding/Day |
| Dawson School | Lafayette | K-12 | Day |
| Denver Academy | Denver | 2-12 | Day |
| Denver Academy of Torah | Denver | K-12 | Day |
| Denver Jewish Day School | Denver | K-12 | Day |
| Eagle Rock School | Estes Park | 9-12 | Boarding |
| Fountain Valley School | Colorado Springs | 9-12 | Boarding/Day |
| High Mountain Institute | Leadville | 11-12 | Boarding |
| International School of Denver | Denver | PreK-12 | Day |
| Kent Denver School | Englewood | 6-12 | Day |
| Shining Mountain Waldorf | Boulder | PreK-12 | Day |
| St. Mary's Academy | Englewood | PreK-12 | Day (girls US) |
| Steamboat Mountain School | Steamboat Springs | K-12 | Boarding/Day |
| Telluride Mountain School | Telluride | PreK-12 | Day |
| The Colorado Springs School | Colorado Springs | PreK-12 | Day |
| The Denver Waldorf School | Denver | PreK-12 | Day |
| Vail Mountain School | Vail | K-12 | Day |
| Watershed School | Boulder | 6-12 | Day |

### Known Colorado BOCES (Incomplete — Most Sites Inaccessible)
~21 BOCES exist in Colorado. Sites attempted:
1. Northwest Colorado BOCES ✓ (accessible, no staff names)
2. Southeast BOCES ✓ (accessible)
3. East Central BOCES ✓ (accessible)
4. Pikes Peak BOCES ✗ (Cloudflare blocked)
5. San Juan BOCES ✗ (inaccessible)
6. Centennial BOCES ✗ (Cloudflare blocked)
7. Northeast Colorado BOCES ✗ (DNS failure)
8. Mount Evans BOCES ✗ (DNS failure)
9. Uncompahgre BOCES ✗ (inaccessible)
10. San Luis Valley BOCES ✗ (inaccessible)
11. Southwest BOCES ✗ (inaccessible)
12. Mountain BOCES ✗ (unknown URL)

**Bottom line:** 40 new contacts across 4 categories. The ACIS umbrella org + 19 private schools with HS programs is the biggest win. BOCES remains a gap that needs browser automation or direct outreach to CDE.
