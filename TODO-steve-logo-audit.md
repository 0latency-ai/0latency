# Steve TODO - Logo Audit

**Priority:** High  
**Created:** March 25, 2026 12:48 PM PST

## Task
Audit ALL pages on 0latency.ai and replace old logos with new SVG wordmark.

**Correct logo:** `/logos/0latency-white-black-text.svg` at 108px height

## Files to Check
- /var/www/0latency/*.html (all HTML files)
- Look for old patterns:
  - `logo-icon.svg` + text in HTML
  - `0latency-logo-light.jpg`
  - Any other logo variants

## Already Fixed
- index.html ✅
- pricing.html ✅
- footer on both pages ✅

## Still Need to Check
- docs.html
- terms.html
- privacy.html
- status.html
- changelog.html
- security.html
- support.html
- demo.html
- login.html
- dashboard.html (if it has a logo)
- Any other pages

## Pattern to Replace
```html
OLD: <img src="/logos/logo-icon.svg" ... > + <span>text</span>
NEW: <img src="/logos/0latency-white-black-text.svg" height="108">
```

**DO THIS SYSTEMATICALLY** - check every page, make a list, fix all at once.
