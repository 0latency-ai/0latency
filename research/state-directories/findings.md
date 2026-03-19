# State Education Directory Research Findings

**Date:** March 11, 2026  
**Purpose:** Build PFL Academy outreach lists from official state education sources  
**States:** Colorado & Texas

---

## TEXAS — AskTED (TEA Official Directory)

### Source Details
- **Primary URL:** `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/Home.aspx`
- **Data Download (School/District):** `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadDefault.aspx`
- **Personnel Download:** `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadFile2.aspx`
- **Site Address Download:** `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/DownloadSite.aspx`
- **ESC Search:** `https://tealprod.tea.state.tx.us/Tea.AskTed.Web/Forms/ESCSearchScreen.aspx`

### What We Downloaded
The **DownloadDefault.aspx** endpoint returns a **complete CSV** of all Texas schools and districts — **no authentication required**. This is the gold mine.

**File:** `texas_raw.csv` (9,761 rows)

**Fields available:**
| Field | Description |
|-------|-------------|
| County Number/Name | County info |
| ESC Region Served | Which of 20 ESC regions |
| District Number/Name | Unique district identifier |
| District Type | Independent, Charter, etc. |
| District Address/City/State/Zip | Mailing address |
| **District Phone** | ✅ Direct phone |
| **District Email Address** | ✅ General district email |
| District Web Page | Website |
| **District Superintendent** | ✅ Full name with title |
| District Enrollment | Oct 2024 count |
| School Number/Name | Individual school |
| Instruction Type | Regular, Alternative, etc. |
| **School Phone/Email** | ✅ School-level contact |
| **School Principal** | ✅ Full name |
| **Grade Range** | Used to filter HS (09-12) |
| School Enrollment | Per-school enrollment |
| School Status | Active/Inactive |

### What We Extracted
| Category | Count |
|----------|-------|
| **Unique Superintendents** | 1,211 |
| **HS Principals** (grade 09-12, regular instruction) | 1,221 |
| **Total contacts** | 2,432 |

### ESC Region Distribution (20 regions)
| Region | Districts | Region | Districts |
|--------|-----------|--------|-----------|
| 01 (Edinburg) | 47 | 11 (Fort Worth) | 95 |
| 02 (Corpus Christi) | 46 | 12 (Waco) | 81 |
| 03 (Victoria) | 37 | 13 (Austin) | 73 |
| 04 (Houston) | 91 | 14 (Abilene) | 43 |
| 05 (Beaumont) | 39 | 15 (San Angelo) | 46 |
| 06 (Huntsville) | 61 | 16 (Amarillo) | 60 |
| 07 (Kilgore) | 101 | 17 (Lubbock) | 61 |
| 08 (Mt. Pleasant) | 46 | 18 (Midland) | 36 |
| 09 (Wichita Falls) | 37 | 19 (El Paso) | 19 |
| 10 (Richardson/Dallas) | 113 | 20 (San Antonio) | 86 |

### Personnel Download (Additional Opportunity)
The `DownloadFile2.aspx` page allows downloading by role type:
- ✅ Principals
- ✅ Superintendents
- ✅ District Staff (with role filter including: CURRICULUM, CTE/CAREER & TECHNICAL EDUCATION, BUSINESS EDUCATION, SOCIAL STUDIES, GUIDANCE/COUNSELING, TEST COORDINATOR, HIGH SCHOOL EDUCATION, SCHOOL IMPROVEMENT, etc.)
- ✅ ESC Staff (same role types)

**⚠️ This requires ASP.NET form POST with ViewState** — not a simple GET download. Options:
1. Use browser automation to submit the form
2. Manual download via browser (click checkboxes, select roles, download)
3. The data includes individual role-specific contacts with personal emails

**RECOMMENDATION:** Have Justin manually visit DownloadFile2.aspx, check "Include Superintendents" + "Include District Staff" (ctrl-select CURRICULUM + CTE + HIGH SCHOOL EDUCATION + GUIDANCE/COUNSELING), and download. This will yield curriculum directors and CTE coordinators with direct emails.

### Sample Data
```
DR JOE E SATTERWHITE III | Superintendent | CAYUGA ISD | superintendent@cayugaisd.com | (903) 928-2102
ZACH WILLIAMS | HS Principal | CAYUGA H S (CAYUGA ISD) | admin1@cayugaisd.com | (903) 928-2294
DR BOBBY AZAM | Superintendent | ANDREWS ISD | bazam@andrews.esc18.net | (432) 523-3640
```

### Limitations
- District email is often a generic address (superintendent@, info@), not personal
- Superintendent names are listed but personal emails require the DownloadFile2.aspx form
- ESC staff contacts require form submission
- Data is refreshed nightly by TEA

---

## COLORADO — CDE (Colorado Department of Education)

### Source Details
- **CDE Homepage:** `https://www.cde.state.co.us/`
- **SchoolView Explore:** `https://www.cde.state.co.us/schoolview/explore/welcome/`
- **Superintendent Resources:** `https://www.cde.state.co.us/superintendents`
- **Superintendent & BOCES Directory (Smartsheet):** `https://app.smartsheet.com/b/publish?EQBCT=0addfc75c63b4c0293fcb2f05340b724`
- **SchoolView District Profiles:** `https://www.cde.state.co.us/schoolview/explore/profile/{district_code}`

### What We Found

#### 1. SchoolView District Profiles (What We Scraped)
Each of Colorado's 215 districts/BOCES has a profile page at SchoolView with:
- Superintendent name
- District enrollment
- Address and city
- Link to district website
- List of schools in district

**We scraped all 215 profiles** and extracted:
| Category | Count |
|----------|-------|
| **Superintendents** | 179 |
| **BOCES Directors** | 5 |
| **Total contacts** | 184 |

31 districts had no superintendent listed (likely vacancies or data gaps).

#### 2. Smartsheet Directory (BEST SOURCE — Not Automated)
CDE publishes an official **Superintendents & BOCES Directors directory** via Smartsheet:
`https://app.smartsheet.com/b/publish?EQBCT=0addfc75c63b4c0293fcb2f05340b724`

**⚠️ This loads dynamically (JavaScript)** — web_fetch returns "Please stand by while loading."

This directory likely contains:
- ✅ Superintendent names
- ✅ Email addresses (personal/direct)
- ✅ Phone numbers
- ✅ District info
- ✅ BOCES directors

**RECOMMENDATION:** Have Justin visit this URL in a browser and export/copy the data. This is the single best Colorado source for superintendent contact info with emails.

#### 3. Special Education Directors List
CDE also publishes a Special Ed Directors list at:
`https://www.cde.state.co.us/cdesped/office-of-special-education/sped-gifted-dir`

While not directly relevant, it shows CDE publishes role-specific directories.

### Colorado BOCES Identified
| BOCES | Director |
|-------|----------|
| Centennial BOCES | Randy Zila |
| Colorado River BOCES | Leon Hanhardt |
| Education reEnvisioned BOCES | Ken Witt |
| Expeditionary BOCES | Tiffany Almon |
| San Juan BOCES | Royce Tranum |

Additional BOCES in SchoolView (no director found in profiles):
- Adams County BOCES
- Arkansas Valley BOCES
- East Central BOCES
- Mountain BOCES
- Pikes Peak BOCES
- South Central BOCES
- Uncompahgre BOCES
- And others (total ~21 BOCES in CO)

### What's Missing from Colorado
- **No downloadable CSV/Excel** for contacts (unlike Texas)
- **No email addresses** in SchoolView profiles
- **No phone numbers** in SchoolView profiles
- **No principal-level data** readily available (would need to visit each school page)
- **Smartsheet has the data** but requires browser access
- No equivalent to AskTED's bulk download

### Sample Data
```
Chris Gdowski | Superintendent | Adams 12 Five Star Schools | District Code: 0020
Karla Loria | Superintendent | Adams County 14 | District Code: 0030
Michael Giles | Superintendent | Adams-Arapahoe 28J | District Code: 0180
Randy Zila | BOCES Executive Director | Centennial BOCES | District Code: 9010
```

### Key Context: HB25-1192 (PFL Mandate)
- Colorado's financial literacy mandate targets Class of 2027
- ICAP (Individual Career and Academic Plan) is the implementation framework
- CTE coordinators and ICAP leads are key decision-makers
- BOCES serve multiple small/rural districts collectively — efficient sales targets

---

## COMPARISON & RECOMMENDATIONS

### Data Quality Summary
| Metric | Texas | Colorado |
|--------|-------|----------|
| Total contacts extracted | 2,432 | 184 |
| Emails included | ✅ (district-level) | ❌ (not in profiles) |
| Phone included | ✅ | ❌ |
| Superintendent names | ✅ (1,211) | ✅ (179) |
| HS Principal names | ✅ (1,221) | ❌ |
| Curriculum/CTE contacts | Available via form | Not available |
| Bulk download | ✅ One-click CSV | ❌ No bulk download |

### Immediate Next Steps

#### Texas (Ready to Use)
1. ✅ `texas_contacts.json` has 2,432 contacts with emails and phones
2. 🔲 **Manual step:** Download from DownloadFile2.aspx to get:
   - Curriculum Director contacts (with personal emails)
   - CTE Coordinator contacts
   - Business Education Coordinator contacts
   - Social Studies Coordinator contacts
3. 🔲 Cross-reference ESC regions for targeted outreach

#### Colorado (Needs Manual Enrichment)
1. ✅ `colorado_contacts.json` has 184 superintendent names
2. 🔲 **Manual step:** Visit the Smartsheet directory to get emails + phones
3. 🔲 Visit district websites to find:
   - CTE Coordinators / ICAP leads
   - Curriculum Directors
   - HS Principals
4. 🔲 Contact BOCES directly — they serve 50+ small districts each
5. 🔲 Check CDE for any downloadable data files in Data Pipeline

### Priority Targets
For PFL Academy's $20/student HS curriculum:

**Texas Top Targets:**
- Large districts (Region 10/Dallas, Region 4/Houston, Region 11/Fort Worth, Region 13/Austin, Region 20/San Antonio)
- Districts with no current PFL curriculum adoption
- ESC staff who train/recommend curriculum to districts

**Colorado Top Targets:**
- BOCES directors (serve many districts, single buying decision)
- Large Front Range districts (Adams 12, Adams-Arapahoe 28J, Cherry Creek, Douglas County, Jefferson County, Denver)
- Districts approaching Class of 2027 deadline without PFL curriculum
