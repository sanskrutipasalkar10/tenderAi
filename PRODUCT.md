# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js 16 (App Router) + Tailwind v4, already scaffolded and running (`frontend/`) —
delegated: chosen in an earlier phase of this project (docs/DECISIONS.md), not a new
decision for this build pass.

## Users

Primary: a bid manager at an Indian EPC/infrastructure contractor, under real deadline
pressure, deciding whether to commit to bidding on a tender worth crores. Secondary:
company leadership reviewing that recommendation before it's acted on. Both are domain
experts in tenders and construction/infra business, not in AI or software — they need
the tool's output to be immediately legible and defensible, not impressive-looking.

## Product Purpose

Reads a full Indian government tender PDF (50-1000+ pages, mixed native text/scanned
images/tables) and produces three outputs a bid team can act on directly: a Go/No-Go
recommendation scored against the company's own profile, a structured synopsis, and a
page-cited risk list. Success is a bid team making a bid/no-bid call in minutes instead
of the days it currently takes to read a tender manually.

## Positioning

Every claim the system makes — every date, amount, criterion, and risk — carries a
citation to the exact source page, re-verified against the real document server-side
before it's ever shown (not just asserted by the model). A competitor that summarizes a
tender without page-level, re-verified citations is asking the bid team to trust it on
faith; this system is built so they never have to.

## Operating Context

A bid manager uploads a tender PDF, waits while it's processed (this can legitimately
take a while for a large document — completeness is prioritized over speed), then
works through the three analysis tabs to build the case for or against bidding, citing
back to the source document as needed to double-check anything before it goes into a
real bid/no-bid decision.

## Capabilities and Constraints

- Auth is a single shared credential for the whole bid team (no per-user accounts,
  confirmed decision — see below). No self-serve signup.
- The system is advisory only: it never submits, emails, or files anything on the
  company's behalf, and never estimates BOQ/pricing.
- Real, live backend already exists and is fully wired (FastAPI + Postgres): document
  upload, per-page classification/extraction, an LLM map-reduce pipeline producing the
  three modules, and a company-profiles CRUD API. This build is a frontend redesign
  over that real, working API — not a mockup.
- No compliance certifications are actually held; do not display badges/claims for
  ones that don't exist.
- No usage statistics exist yet (new product) — do not display invented numbers.

## Brand Commitments

Product name: "Tender AI Platform" (working name, not a designed wordmark — a real
logo/wordmark is out of scope for this pass). No existing visual identity to preserve;
this build establishes it for the first time.

## Evidence on Hand

None yet — no real customer testimonials, logos, or case studies exist for this
pre-launch product. The landing page must not fabricate any.

## Product Principles

1. Every AI claim is traceable to a real source page — this is the actual trust
   mechanism, not a decorative feature, and must never be visually buried.
2. Advisory, not autonomous: the system surfaces information for a human to decide on;
   it never implies it has made or will act on the decision itself.
3. Built for a domain expert under deadline pressure evaluating financial/legal risk on
   large decisions — clarity and information density over decoration.
4. Never invent what isn't real: no fabricated stats, testimonials, compliance badges,
   or a fourth risk-severity tier the backend doesn't actually produce.

## Accessibility & Inclusion

No product-specific requirement established beyond standard web accessibility
practice (keyboard navigation, sufficient color contrast, semantic markup) — expected
for a Tier 2 internal/pilot tool used by a professional team, not separately confirmed.
