# Frontend — Tender AI Platform

Next.js 16 (App Router) + Tailwind v4. Upload a tender, view its Go/No-Go /
Synopsis / Risk Finder analysis in tabs, and click any fact's `p.N` citation to see
the real source page — that citation click-through is this project's actual HITL
mechanism (`docs/SPEC.md`'s HITL note; there's no separate approve/override workflow).

## Run locally

```bash
cp .env.example .env.local   # NEXT_PUBLIC_API_URL, defaults to http://localhost:8000
npm install
npm run dev
```

The backend (`../backend`) must be running and reachable at `NEXT_PUBLIC_API_URL`, with
`CORS_ALLOWED_ORIGINS` on the backend including this frontend's origin (docs/
DECISIONS.md #56) — without it, every request is silently blocked by the browser
before the backend ever sees it.

## Structure

- `lib/types.ts` — mirrors `backend/app/models/schemas.py` field-for-field.
- `lib/api.ts` — the one place that calls the backend; attaches the JWT, handles 401
  by clearing the token and redirecting to `/login`.
- `lib/auth.ts` / `lib/useAuthState.ts` — the shared-credential JWT lives in
  `localStorage` (docs/DECISIONS.md #44); `useAuthState` reads it via
  `useSyncExternalStore` for a hydration-safe render (see its own comment for why a
  naive `useEffect` + `setState` approach redirects prematurely).
- `components/CitationLink.tsx` — the HITL mechanism. Portaled to `document.body`
  (docs/DECISIONS.md #57) since it's used inline inside prose (a `<p>`/`<td>`), where
  rendering the modal in place would nest block elements inside an inline element —
  invalid HTML, found via a real browser hydration-error warning, not inspection.
- `components/{GoNoGoCard,SynopsisView,RiskList}.tsx` — one per reduce-pass module,
  rendering exactly what the API returns.

## What's been verified for real

Unlike the Langfuse/Prometheus config in Phase 8 (no Docker in that dev sandbox to
verify against), this frontend WAS driven end-to-end in a real headless browser
(Playwright) against the real running backend and real Postgres data: login-form
render, the unauthenticated redirect, a real CORS preflight, real document list/detail
rendering with actual analysis from actual documents, and a real citation click
opening a real source page. Two real bugs were found and fixed this way — an
`AuthGuard` redirect race on first hydration, and `CitationLink`'s modal producing
invalid HTML when used inline in prose — neither of which `next build`/`tsc`/ESLint
would ever have caught. See `docs/DECISIONS.md` #56-57.

**Not yet built:** a `company-profile` page (creating/editing a `company_profiles` row
from the UI — `scripts/seed_company_profile.py` is the only way to do this today).
