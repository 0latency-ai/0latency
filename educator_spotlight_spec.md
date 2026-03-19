# Educator Spotlight Page — Component Specification

**Page:** `/educators` or `/spotlight`
**Stack:** React + TypeScript + Vite + Tailwind CSS
**Design System:** PFL Academy palette, Ras Mic UI library (north star)
**Status:** Spec only — no code yet

---

## 1. Page Layout Overview

```
┌─────────────────────────────────────────────┐
│              Hero / Page Header              │
│  "Hear From Educators Using PFL Academy"    │
├─────────────────────────────────────────────┤
│                                             │
│         Casey Perez — Video Spotlight        │
│   [Video Embed]  [Pull Quotes]  [Bio]       │
│                                             │
├─────────────────────────────────────────────┤
│                                             │
│      Dianna Wilkins — Written Spotlight      │
│   [Headshot]  [Testimonial]  [Bio]          │
│                                             │
├─────────────────────────────────────────────┤
│         CTA Section / Bottom Banner          │
│   "See what PFL Academy can do for your     │
│    classroom"                                │
└─────────────────────────────────────────────┘
```

**Single-page scroll layout.** No tabs, no routing between educators. Each educator gets a full-viewport (or near-full) section. As the roster grows, new sections are appended. Future: paginated or filtered view when >5 educators.

---

## 2. Design Specifications

### Color Palette

| Token | Hex | Usage |
|---|---|---|
| `primary-700` | `#4338ca` | Headlines, CTA buttons, active states |
| `primary-600` | `#4F46E5` | Links, hover states, secondary accents |
| `primary-500` | `#6d28d9` | Gradient midpoint, decorative elements |
| `gradient-hero` | `#4338ca → #6d28d9` | Hero background gradient (left to right) |
| `gradient-accent` | `#4338ca → #4F46E5` | Button gradients, quote card accents |
| `neutral-50` | `#f9fafb` | Page background |
| `neutral-100` | `#f3f4f6` | Card backgrounds, alternating sections |
| `neutral-700` | `#374151` | Body text |
| `neutral-900` | `#111827` | Headlines |
| `white` | `#ffffff` | Card surfaces, text on dark backgrounds |

### Typography

**Design philosophy (Ras Mic):** "Your config doesn't just change colors. It rewrites the component code to match your setup. Font, spacing, structure." Every Shadcn app defaults to Inter — that's exactly why we don't use it. PFL Academy should have its own typographic identity so it doesn't look like every other component-library app on the internet.

**Font stack:**
- **Display / Headings:** Plus Jakarta Sans — geometric, modern, highly legible at large sizes. Distinctive character shapes (especially the lowercase 'a' and 'g') that set it apart from Inter/system sans without sacrificing readability.
- **Body / UI:** Geist Sans — Vercel's own typeface, designed for interfaces. Clean and neutral but with subtle personality in its proportions. Pairs naturally with Plus Jakarta Sans.
- **Pull quotes / Editorial:** Newsreader — a variable serif designed for on-screen reading. More refined than Georgia, with optical sizing built in. Gives testimonials the editorial weight they deserve.
- **Monospace (future use):** JetBrains Mono — Ras Mic's pick in his Shadcn Create demo. For any code snippets, data tables, or technical UI elements we add later. Ligatures enabled by default.

**Loading:** All fonts loaded via `@fontsource` packages (self-hosted, no Google Fonts network dependency). Critical weights preloaded in `<head>`. Fallback chain: `Plus Jakarta Sans → Geist Sans → system-ui → sans-serif` for headings, `Geist Sans → system-ui → sans-serif` for body.

| Element | Font | Size (mobile / desktop) | Weight | Line Height |
|---|---|---|---|---|
| Page title (H1) | Plus Jakarta Sans | 28px / 40px | 800 (extrabold) | 1.2 |
| Educator name (H2) | Plus Jakarta Sans | 24px / 32px | 700 (bold) | 1.25 |
| Section subtitle | Geist Sans | 16px / 18px | 500 (medium) | 1.5 |
| Body text | Geist Sans | 15px / 16px | 400 (regular) | 1.6 |
| Pull quote text | Newsreader | 18px / 22px | 400 (regular) | 1.5 |
| Pull quote attribution | Geist Sans | 13px / 14px | 500 (medium) | 1.4 |
| Bio details (role, school) | Geist Sans | 13px / 14px | 400 (regular) | 1.5 |
| Monospace (data/code) | JetBrains Mono | 13px / 14px | 400 (regular) | 1.5 |

### Spacing System

- Section padding: `py-16 md:py-24` (64px / 96px vertical)
- Content max-width: `max-w-6xl` (1152px) centered
- Card padding: `p-6 md:p-8`
- Gap between elements: `space-y-6` or `gap-6` standard
- Quote card left border: `border-l-4 border-primary-700`

### Elevation & Effects

- Cards: `shadow-sm` default, `shadow-md` on hover (150ms ease transition)
- Video container: `rounded-xl overflow-hidden shadow-lg`
- Quote cards: No shadow — rely on left border accent and subtle background (`bg-neutral-50`)
- Section dividers: None. Alternate section backgrounds (`white` / `neutral-50`) for visual separation.

---

## 3. Section Specifications

### 3.1 Hero / Page Header

**Layout:** Full-width, gradient background (`#4338ca → #6d28d9`), white text.

**Content:**
- H1: "Hear From Educators Using PFL Academy"
- Subtitle: "Real teachers. Real classrooms. Real results."
- No CTA button in hero — let the content pull them down.

**Height:** `min-h-[280px] md:min-h-[360px]` — substantial but not full-viewport.

**Mobile:** Stack centered. Reduce font sizes per typography table.

---

### 3.2 Casey Perez — Video Spotlight Section

**Background:** White (`bg-white`)

**Layout (Desktop — md+):**
```
┌──────────────────────────────────────────────┐
│                                              │
│  ┌─────────────────┐  ┌──────────────────┐   │
│  │                 │  │  Bio Card         │   │
│  │  YouTube Video  │  │  Name, role,      │   │
│  │  Embed          │  │  school, years    │   │
│  │  (16:9)         │  │                   │   │
│  │                 │  │                   │   │
│  └─────────────────┘  └──────────────────┘   │
│                                              │
│  ┌──────────────────────────────────────────┐ │
│  │  Pull Quotes (horizontal scroll or grid) │ │
│  │  [Quote 1] [Quote 2] [Quote 3] [Quote 4]│ │
│  └──────────────────────────────────────────┘ │
│                                              │
└──────────────────────────────────────────────┘
```

**Layout (Mobile):**
```
┌────────────────────┐
│  YouTube Video     │
│  (16:9, full-width)│
├────────────────────┤
│  Bio Card          │
│  (full-width)      │
├────────────────────┤
│  Quote 1           │
├────────────────────┤
│  Quote 2           │
├────────────────────┤
│  Quote 3           │
└────────────────────┘
```

#### Video Embed

- **Source:** `https://youtu.be/DcDT4qTphVc`
- **Embed:** YouTube iframe via `https://www.youtube-nocookie.com/embed/DcDT4qTphVc` (privacy-enhanced mode)
- **Aspect ratio:** 16:9, maintained via `aspect-video` Tailwind class
- **Container:** `rounded-xl overflow-hidden shadow-lg`
- **Width:** 60% on desktop (`md:w-3/5`), 100% on mobile
- **Loading:** `loading="lazy"` on iframe. Show a placeholder thumbnail (from YouTube API: `https://img.youtube.com/vi/DcDT4qTphVc/maxresdefault.jpg`) until interaction.
- **Interaction:** Click thumbnail → replace with iframe (reduces initial page load). Play button overlay centered on thumbnail.
- **Accessibility:** `title="Casey Perez discusses PFL Academy in his alternative education classroom"`

#### Bio Card

- **Position:** Right of video on desktop, below on mobile
- **Content:**
  - Name: **Casey Perez**
  - Role: Alternative Education Counselor / Director / Capstone Teacher
  - School: Clinton Public Schools, Oklahoma
  - Experience context: "3 years in alternative education. First year teaching financial literacy with PFL Academy."
  - Small PFL Academy logo or badge: "PFL Academy Educator"
- **Style:** `bg-neutral-50 rounded-xl p-6`, no shadow
- **Width:** 40% on desktop (`md:w-2/5`), 100% on mobile

#### Pull Quotes

**Selected quotes (4):**

1. > *"It's been kind of hodgepodged before. This is the first year that we've had a packaged program for financial literacy."*
   — On the problem

2. > *"They take over that discussion. I don't have to prompt them a whole lot. The kids are definitely getting it."*
   — On student engagement

3. > *"He came back and told me — that was amazing. I didn't feel intimidated by anything. I felt like I understood what was going on."*
   — On student confidence (student navigating a bank conversation)

4. > *"Highly recommended. It's in such an understandable way for the teacher and the student. It drives questions that you wouldn't even think about."*
   — On recommending PFL Academy

**Quote display: Static grid, NOT a carousel.**

Rationale: Carousels hide content and reduce engagement. All quotes should be visible. On desktop: 2×2 grid. On mobile: vertical stack.

**Quote card design:**
- `border-l-4 border-primary-700 bg-neutral-50 rounded-r-lg p-5`
- Quote text in serif font (Georgia), italic
- Attribution line below: educator name, role, school — in sans-serif, `text-sm text-neutral-500`
- Hover: `border-l-primary-600` color shift + subtle `translate-x-1` (2px right nudge, 200ms ease)

---

### 3.3 Dianna Wilkins — Written Spotlight Section

**Background:** `bg-neutral-50` (alternating from Casey's white section)

**Layout (Desktop):**
```
┌──────────────────────────────────────────────┐
│                                              │
│  ┌──────────┐  ┌────────────────────────┐    │
│  │ Headshot │  │  Featured Testimonial   │    │
│  │ (square) │  │  (large pull quote)     │    │
│  │          │  │                         │    │
│  │          │  │  Bio details below      │    │
│  └──────────┘  └────────────────────────┘    │
│                                              │
└──────────────────────────────────────────────┘
```

**Layout (Mobile):**
```
┌────────────────────┐
│  Headshot (centered)│
├────────────────────┤
│  Featured Quote    │
│  (full-width)      │
├────────────────────┤
│  Bio details       │
└────────────────────┘
```

#### Headshot

- **Status:** PLACEHOLDER — headshot needs to be collected
- **Placeholder:** Gradient circle (`bg-gradient-to-br from-primary-700 to-primary-500`) with initials "DW" in white, centered
- **Final:** Square crop, `rounded-2xl`, `w-48 h-48 md:w-64 md:h-64`, `object-cover`
- **Border:** `ring-4 ring-white shadow-lg` to lift off the neutral background

#### Testimonial

- **Status:** PLACEHOLDER — written testimonial needs to be collected from Dianna
- **Placeholder text:** *"Testimonial coming soon. Dianna Wilkins has been teaching financial literacy at Dale High School for over a decade and was among the first educators to adopt PFL Academy."*
- **Final format:** Large pull quote style, same serif font as Casey's quotes but larger (`text-xl md:text-2xl`)
- **Design:** Opening large quotation mark graphic (decorative, `text-primary-700 text-6xl opacity-20`) positioned top-left of quote block

#### Bio Card

- Name: **Dianna Wilkins**
- Role: Financial Literacy Teacher
- School: Dale High School, Oklahoma
- Experience: "12-year veteran teacher. Among the first educators to adopt PFL Academy."
- Badge: "PFL Academy Educator"
- Same styling as Casey's bio card

---

### 3.4 CTA Section / Bottom Banner

**Background:** Gradient (`#4338ca → #4F46E5`), white text

**Content:**
- H2: "Ready to see what PFL Academy can do for your classroom?"
- Subtitle: "Standards-aligned. ICAP/ILP integrated. Built for real teachers."
- Primary CTA button: "Request a Demo" → links to demo/contact page
- Secondary CTA (text link): "Explore the Free Tier" → links to free resources
- Button style: `bg-white text-primary-700 font-semibold px-8 py-3 rounded-full shadow-md hover:shadow-lg hover:scale-[1.02] transition-all duration-200`

---

## 4. Component Breakdown

### Component Tree

```
<EducatorSpotlightPage>
  ├── <SpotlightHero />
  ├── <EducatorSection variant="video">
  │     ├── <VideoEmbed videoId="DcDT4qTphVc" />
  │     ├── <EducatorBio educator={caseyPerez} />
  │     └── <QuoteGrid quotes={caseyQuotes} />
  ├── <EducatorSection variant="written">
  │     ├── <EducatorHeadshot src={...} fallbackInitials="DW" />
  │     ├── <FeaturedTestimonial quote={...} />
  │     └── <EducatorBio educator={diannaWilkins} />
  └── <SpotlightCTA />
```

### Component Descriptions

| Component | Props | Description |
|---|---|---|
| `EducatorSpotlightPage` | — | Page-level layout. Manages section ordering and backgrounds. |
| `SpotlightHero` | `title`, `subtitle` | Gradient hero banner. Pure presentational. |
| `EducatorSection` | `variant: 'video' \| 'written'`, `bgColor`, `educator` | Wrapper that handles layout switching between video-first and written-first formats. Alternates background color. |
| `VideoEmbed` | `videoId: string`, `title?: string` | YouTube embed with lazy-load thumbnail → iframe swap on click. Handles 16:9 aspect ratio. |
| `EducatorBio` | `educator: EducatorData` | Displays name, role, school, experience, badge. Reusable across all educator sections. |
| `QuoteGrid` | `quotes: Quote[]`, `columns?: 1 \| 2` | Renders pull quotes in responsive grid. 2 columns on md+, 1 on mobile. |
| `QuoteCard` | `quote: Quote` | Individual quote with left border accent, serif text, attribution. Hover animation. |
| `EducatorHeadshot` | `src?: string`, `fallbackInitials: string`, `alt: string` | Image with gradient initial fallback when no src provided. |
| `FeaturedTestimonial` | `quote?: string`, `placeholder?: boolean` | Large-format pull quote with decorative quotation mark. Shows placeholder state when quote is pending. |
| `SpotlightCTA` | `primaryHref`, `secondaryHref` | Gradient banner with two CTA options. |

### TypeScript Interfaces

```typescript
interface EducatorData {
  name: string;
  role: string;
  school: string;
  district: string;
  state: string;
  experienceNote: string;  // e.g. "12-year veteran teacher"
  headshotUrl?: string;    // optional — shows initials fallback if missing
  initials: string;
  videoId?: string;        // YouTube video ID if they have a video testimonial
}

interface Quote {
  text: string;
  context: string;         // e.g. "On student engagement"
  educatorName: string;
  educatorRole: string;
  educatorSchool: string;
}
```

---

## 5. Responsive Behavior Summary

| Breakpoint | Layout Changes |
|---|---|
| `< 640px` (mobile) | Single column everything. Video full-width. Bio below video. Quotes stacked vertically. Headshot centered above testimonial. Hero text centered, smaller. |
| `640px–768px` (sm) | Same as mobile but with more horizontal padding. |
| `768px–1024px` (md) | Video + Bio side-by-side (60/40). Quotes in 2-column grid. Headshot + Testimonial side-by-side. |
| `> 1024px` (lg) | Max-width container (`max-w-6xl`). Same layout as md but with more generous spacing. |

---

## 6. Interaction Details

### Video Embed
- **Default state:** YouTube thumbnail with centered play button overlay (custom SVG, white triangle in semi-transparent dark circle)
- **Hover:** Play button scales up `scale-110`, circle opacity increases. Thumbnail gets subtle `brightness-90` dim.
- **Click:** Thumbnail replaced with YouTube iframe, autoplay enabled (`?autoplay=1&rel=0`)
- **Focus (keyboard):** Outline ring on play button, Enter/Space triggers play

### Quote Cards
- **Default:** Left border `#4338ca`, white background
- **Hover:** Border shifts to `#4F46E5`, card nudges right 2px (`translate-x-0.5`), transition 200ms ease
- **Focus (keyboard):** Same visual treatment as hover + focus ring

### CTA Buttons
- **Default:** White background, primary text color, medium shadow
- **Hover:** Larger shadow, slight scale-up (`scale-[1.02]`), 200ms transition
- **Active/Click:** Scale back to `scale-100`, shadow reduces — tactile press feel
- **Focus:** Ring outline `ring-2 ring-white ring-offset-2 ring-offset-primary-700`

### Headshot (Dianna — placeholder state)
- **Default:** Gradient circle with initials, subtle pulse animation (`animate-pulse` at low opacity) to signal "coming soon"
- **When real image available:** Remove pulse, show image with smooth fade-in on load

### Scroll Behavior
- No scroll-jacking. Native browser scroll.
- Optional: `scroll-mt-8` on section anchors for jump-link offset if nav is added later.

---

## 7. Accessibility Requirements

- All images: meaningful `alt` text
- Video iframe: descriptive `title` attribute
- Quote cards: semantic `<blockquote>` with `<cite>` for attribution
- Color contrast: All text meets WCAG AA (verified: white on `#4338ca` = 8.6:1, `#374151` on white = 10.3:1)
- Keyboard navigation: All interactive elements focusable with visible focus indicators
- Reduced motion: `prefers-reduced-motion` media query disables hover translations and pulse animations

---

## 8. Data Notes & Open Items

| Item | Status | Owner |
|---|---|---|
| Casey Perez video | ✅ Available | `https://youtu.be/DcDT4qTphVc` |
| Casey Perez quotes | ✅ Extracted | See `casey_perez_key_quotes.md` |
| Casey Perez headshot | ❌ Not available | Pull frame from video or request |
| Dianna Wilkins testimonial | ❌ Not collected | Justin/Thomas to collect |
| Dianna Wilkins headshot | ❌ Not available | Justin/Thomas to collect |
| Demo page URL | ❌ TBD | For CTA link target |
| Free tier URL | ❌ TBD | For secondary CTA |
| Analytics events | ❌ Not specified | Track: video play, CTA clicks, scroll depth |

---

*Spec prepared by Steve, CMO — PFL Academy. March 2026.*
*Ready for Sebastian (dev) to implement once assets are collected.*
