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

## Provenance

Built code-led (no image generation available in this environment) — the ambition
lives in this contract and the shipped build, audited in behavior at finish, not
against a pre-rendered comp. Revision 2 additionally grounded itself in the real,
fetched CSS of the named reference site rather than a description of it.
