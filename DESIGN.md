# Design

## Direction contract

**THESIS:** Every number and claim on screen is a verifiable fact with a page
citation, not a generated summary to trust on faith — the surface refuses the
generic "AI insights card" look (soft gradient panel, rounded pill confidence score,
no way to check the underlying source) that this category defaults to.

**OWN-WORLD:** Blueprint precision. Ink-navy ground (`#0B1220`), not pure black or
warm cream. One committed cyan-blue accent (`#2DD4E8`-family) doing the work
blueprint linework does — precision, structure, verifiability — never a decorative
gradient. Crisp 1px rule lines and real borders, not soft drop-shadows. IBM Plex Sans
for UI text, IBM Plex Mono specifically for every verifiable data point (scores,
amounts, dates, page citations) so a reader can visually tell "claim" from "generated
prose" at a glance without reading it.

**STORY:** A bid manager under deadline pressure opens a tender, sees an immediate
Go/No-Go read, and can trace any single fact back to its real source page in one
click — never left wondering whether a number is real or generated.

**FIRST VIEWPORT (landing):** Dark ink-navy hero, headline + subhead in Plex Sans at
high contrast, primary CTA in the cyan accent. No stats strip (none are real yet).

**FIRST VIEWPORT (analysis workspace):** A circular Go/No-Go gauge (0-100, cyan arc
on ink) anchors the top-left of the tab; the decision label reads at a glance from
across a desk. Citation links are cyan, monospace-tagged `p.N`, and never buried in
body-text color.

**FORM:** Restrained color strategy (neutrals + one accent) — this is primarily an
Operate/Read surface (a working tool under deadline pressure), not a Persuade
surface; the landing page borrows the same world rather than switching languages.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its
provenance.

## Tokens

- `--ink-950: #0B1220` — primary dark ground (hero, sidebar-dark contexts)
- `--ink-900: #111827`
- `--paper: #F7F8FA` — light-mode ground (the working tool itself is light by
  default; ink-950 is reserved for the marketing hero and dark-mode)
- `--accent: #0891B2` (cyan-700, light-mode-safe contrast) / `--accent-bright:
  #2DD4E8` (dark-mode / hero use)
- Severity: HIGH `#DC2626` (red-600), MEDIUM `#D97706` (amber-600), LOW `#64748B`
  (slate-500 — deliberately not green; "low" risk is still risk, not "safe")
- Status: Go `#16A34A` (green-600), Conditional-Go `#D97706` (amber-600), No-Go
  `#DC2626` (red-600)
- Fonts: IBM Plex Sans (UI/body/headings), IBM Plex Mono (every verifiable data
  point: scores, amounts, dates, page citations, IDs)

## Revision 2 — ContraVault-inspired polish pass

The user flagged the first build as "very basic" and pointed at
[contravault.com](https://www.contravault.com/) (a real competitor in this exact
category — tender/RFP analysis for construction/EPC) as the bar to hit. Fetched the
live page's actual CSS (not just a visual glance) to ground this in real values rather
than vibes: their landing page runs on a literal design-token stylesheet exposing
`--gray-00` through `--gray-1000`, an explicit type scale (H1 62-72px, medium/500
weight, `-0.02em` tracking), a tight 4-6px radius scale (`--radius-button: 4px`,
`--radius-card: 4px`, `--radius-pill: 999px`), and a single accent (`#19D67C`, a green)
used sparingly against near-white/near-black neutrals — never a gradient, never a
generic SaaS blue.

**What was borrowed (the structural/typographic principles):**
- Large + medium-weight headlines read as more confident/precise than large + bold —
  applied via `.heading-tight` (`-0.02em`) and dropping hero weight from `font-bold`.
- A tight, precise radius scale (4-6px on buttons/cards/inputs) rather than the
  softer, more "consumer SaaS" `rounded-lg` (8px) used everywhere in the first pass.
- Text links with a trailing arrow for secondary actions, filled buttons reserved for
  the one primary action per section (already implicit in `CitationLink`, made
  explicit elsewhere).
- "Prove it, don't just claim it" — ContraVault embeds a live upload widget directly
  in its hero instead of stock photography. This product's hero can't embed a real
  authenticated upload flow, so instead it embeds a real, non-fabricated UI preview
  built from the actual `ScoreGauge`/badge components (illustrative labels, no
  invented performance stats — still holds the line from Revision 1).

**What was deliberately NOT borrowed:** their exact palette (`#19D67C` green, warm
off-white canvas) and their commercial fonts (Gilroy/Satoshi, not available as
web-safe or Google Fonts). This product keeps its own committed identity — ink-navy +
cyan accent — and swaps only the UI typeface, from IBM Plex Sans to **Manrope**, a
free/Google-Fonts geometric-humanist grotesk with the same tighter, more precise
letterform quality ContraVault's Satoshi has, without cloning a competitor's specific
brand fonts or color identity. IBM Plex Mono remains reserved for verifiable data
(Revision 1's still load-bearing distinction).

## Revision 3 — Indigo Precision

A real audit (reading every route's code, reading this doc, and screenshotting all 6
routes in a real browser via Playwright MCP against the real running app/backend/data)
found a consistency gap Revisions 1/2 hadn't addressed: the marketing landing page got
real, deliberate design attention, but the actual working app — Dashboard, Upload,
Company Profile, the tender analysis workspace, i.e. where a user spends nearly all
their time — was markedly plainer: flat grey/white boxes, large dead whitespace, and
no shared Button/Card/Input components anywhere (every button/card was hand-copied
Tailwind utility classes, styled slightly differently in 5+ places — confirmed by grep,
not estimated). The user, asked directly, chose a full palette change over extending
the existing cyan/navy identity, and chose full scope (landing page included, not just
the app).

**New tokens** (same names as Revisions 1/2 — `ink-950`/`ink-900`/`paper`/`accent`/
`accent-bright` — only the hex values moved, so 144 existing call sites across 17 files
repainted for free with zero per-file edits):
- `--ink-950: #0f1115` — near-black graphite (was `#0b1220` ink-navy)
- `--ink-900: #1c1d21` — primary text on light grounds (was `#111827`)
- `--paper: #fafaf6` — warm off-white (was `#f7f8fa`)
- `--accent: #4f46e5` / `--accent-bright: #818cf8` — indigo (was `#0891b2`/`#2dd4e8` cyan)

**Deliberately unchanged**: severity colors (HIGH red/MEDIUM amber/LOW slate) and
status colors (Go green/Conditional amber/No-Go red) — these are meaningful risk/
decision signals, not brand colors, and changing them would be a real regression in
"can a reviewer tell severity at a glance." The mono-for-verifiable-data rule, the
tight radius scale, and the citation-link visual treatment (dotted underline + `p.N`
mono chip) are all unchanged too — the verifiability thesis doesn't change with the
palette.

**New shared primitives** (`frontend/components/ui/`, none existed before this
revision): `Card`, `Button` (5 variants + a `success` variant added specifically for
the "Mark eligible"/"Mark not eligible" review pair, `loading` state, both `<button>`
and `next/link` rendering), `Tabs`, `Field`/`Input`/`Select`, `PageHeader`,
`EmptyState`, `Spinner`, a small hand-rolled `icons.tsx` (matching the existing
stroke conventions already in the codebase rather than pulling in an icon library for
~12 icons). Migrated onto them: every page and 8 of the 11 existing components. Also
fixed while touching these files: 8 stray hardcoded `hover:bg-cyan-600`/`to-cyan-200`
literals that bypassed the token system entirely (would have visibly flashed the old
cyan on hover/gradient even after the palette swap), and `ProcessingLog.tsx`'s
dark-card-with-light-border mismatch (`border-slate-200` on a `bg-ink-950` panel).

**Worst-first migration** (per the user's explicit priority): `CompanyProfileForm.tsx`
(774 lines, 10 previously-ungrouped sections — now each wrapped in its own `Card`,
turning one dense continuous form into a scannable stack; the native `<input
type="date">` was also swapped for a styled text input with a `DD-MM-YYYY` hint,
purely visual, no validation change) → `/upload` (was the sparsest page, a small
dropzone floating alone in a large empty page — now a 2-column layout with a
"what happens next" panel reusing the landing page's own step copy via a new shared
`lib/steps.ts`, so the authenticated flow finally shares language with the marketing
page) → `/dashboard` (table wrapped in `Card`, gained a left-border accent per row
color-coded by Go/No-Go decision for at-a-glance scannability — verified against the
real, intentionally-untouched messy data: duplicate filenames, stuck-Processing rows,
per the user's explicit "styling only, don't touch data" constraint) → the analysis
workspace (`documents/[id]` + `GoNoGoCard`/`SynopsisView`/`CompanyChecklistView`/
`RiskList`/`ProcessingPipeline`/`ProcessingLog`/`CitationLink`; `GoNoGoCard`'s Overview
tab also gained a persistent "Decision factors" strip — a compact horizontal-bar
breakdown of the 8 weighted factors, built from data the page already fetches — since
before this it could render as a single near-orphaned gauge card with a lot of dead
space below it whenever a document had no gaps to show) → `AppShell` nav (logo/buttons
migrated onto the new primitives; nav links gained an active-pill background;
**`AuthGuard` → `TopBar` → `<main>` composition deliberately left untouched** — every
authenticated page's auth gate depends on it) → `/login` and `/` landing (lightest
touch, recolor + fix their stray literals only — both already worked well; verified in
a real browser that `/`'s `framer-motion` `whileInView` scroll reveals still fire
correctly for a real scrolling user, since a full-page Playwright screenshot had
initially made them look broken — that was a screenshot-capture artifact, not a real
bug, confirmed by scrolling and re-screenshotting the actual viewport).

**Verified in a real browser** (Playwright MCP, real dev server, real backend, real
seeded data — 22 documents, 1 company profile "C4i4 Lab"), not just `npm run build`:
every redesigned page screenshotted against real data (including the intentionally
messy dashboard rows and the data-dense company profile), all 4 analysis-workspace
tabs plus both GoNoGoCard sub-tabs plus all 4 CompanyChecklistView sub-tabs clicked
through, the `CitationLink` modal opened against a real source page, the log-out flow
exercised end-to-end (confirms `AuthGuard` still redirects correctly), and a mobile
viewport (390px) checked for `/dashboard` and `CompanyProfileForm` specifically as the
two most layout-sensitive redesigned surfaces. `npm run build`/`npm run lint` kept
clean after every phase, not just at the end.

## Revision 4 — pulled landing/login design (navy/cobalt, `/` and `/login` only)

The user designed a separate landing/login treatment in Lovable (a TanStack Start +
shadcn/ui project, repo `sanskrutipasalkar10/tender-scan-ace`) and asked for it to
replace Revision 3's landing/login pages, discarding that version. Explicitly scoped
by the user to `/` and `/login` only — the rest of the app (Dashboard, Upload, Company
Profile, the analysis workspace) **keeps the Revision 3 Indigo Precision palette**;
extending navy/cobalt everywhere else was offered and declined for now, so the app
currently has two deliberate, separately-scoped visual identities: an editorial
marketing pair (`/`, `/login`) and an operate/read working-tool pair (everything
authenticated). Flagged as a real, known inconsistency, not an oversight.

**New tokens, additive only** (no existing Revision 3 token was renamed or
repointed — `bg-navy`/`text-cobalt`/etc. are new Tailwind utilities that only the
ported pages reference, so nothing elsewhere in the app was touched):
`navy` (`oklch(0.246 0.031 245)`), `cobalt` (`oklch(0.485 0.184 260)`), `cobalt-light`
(`oklch(0.905 0.015 225)`), `surface` (pure white), `success`/`success-surface`,
`warning`/`warning-surface`, `danger`/`danger-surface`, plus a new `--font-display`
(Sora, loaded via `next/font/google` alongside the existing Manrope/IBM Plex Mono, not
a `<link>` tag) for headlines — Manrope stays the body font on these two pages too, per
the source design. The existing `bg-paper` token (Revision 3's warm off-white) was
reused for these pages' background rather than adding a near-duplicate "paper" token —
visually indistinguishable from the source's own `oklch(0.974 0.004 225)` paper.

**New dependency**: `lucide-react` — the source design's icons; added rather than
hand-rolling ~12 icon shapes to match a design that isn't ours to freely reinterpret.
Ported as a straight visual port, not a re-design: same layout, same copy, same
editorial button variants (rebuilt as plain Tailwind classes on native `<Link>`/
`<button>` elements rather than importing the source's `cva`/`@radix-ui/react-slot`
button component, since only two pages need it), same CSS-keyframe entrance/scan
animations (`rise-in`/`document-scan`/`soft-pulse`, ported verbatim into `globals.css`
as Tailwind v4 `@utility` blocks, including the source's own `prefers-reduced-motion`
guard — these are plain CSS, not `framer-motion`, so they needed their own guard
independent of `app/layout.tsx`'s existing `MotionConfig`). The one real-content
substitution: `/login`'s form now calls this app's actual `lib/api.ts` `login()` and
routes to `/dashboard` on success — the source project's login was a visual stub
(`"Sign-in is not connected yet"`, nothing sent or saved), since real auth was never
that project's job.

**Verified in a real browser** against the real backend, not just visually: submitted
the login form with deliberately wrong credentials and confirmed a real `401` came
back through the actual API and rendered in the new `danger`/`danger-surface` styling
("Incorrect username or password") — confirming the port didn't just look right but
that the real auth call-and-error path survived the rewrite intact. Password
show/hide toggle also exercised directly. `npm run build`/`npm run lint` clean.

## Provenance

Built code-led (no image generation available in this environment) — the ambition
lives in this contract and the shipped build, audited in behavior at finish, not
against a pre-rendered comp. Revision 2 additionally grounded itself in the real,
fetched CSS of the named reference site rather than a description of it. Revision 3
was grounded the same way — real screenshots of the actual running app, not a
description of what it probably looked like — and the finish review above is itself
that audit, not a claim taken on faith.
