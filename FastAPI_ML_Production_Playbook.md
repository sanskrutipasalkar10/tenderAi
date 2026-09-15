# FastAPI + ML Production Playbook
### Read this before starting any new project — a checklist to apply every concept from your FastAPI course

> **Revision note:** The first version leaned heavily on the Capstone project's structure and under-covered the earlier, more conceptual chapters. Below is what was missing, now folded into the phases above (look for **[Added]**/**[Corrected]** tags) instead of listed separately, so the doc stays one linear checklist rather than a checklist plus an addendum you have to cross-reference.

**What was missing:**
1. **API protocol choice** — REST was assumed by default; REST/GraphQL/gRPC/WebSocket/SOAP each have real use cases → Phase 1
2. **API lifecycle & governance** — versioning strategy, API gateways (Kong/AWS API Gateway/Apigee), design/doc tooling → Phase 1
3. **Rate limiting & quotas** (`X-RateLimit-*` headers) → Phase 2 & 5
4. **Full auth landscape** — only JWT + API keys were covered; OAuth 2.0/OIDC, Bearer tokens, refresh tokens, and MFA were missing entirely → Phase 5
5. **A wrong claim**: the original doc said to use `async def` for "model inference if it supports it" — the course notes are explicit that ML inference is CPU-bound and should use plain `def`, not `async def` → Phase 2 **[Corrected]**
6. **Pydantic `Field`-level validation** (`Field`, `StrictInt`/`StrictFloat`, `Optional`) → Phase 2
7. **E2E tests** — only unit + integration were listed → Phase 6
8. **The common API error catalog** (401/404/422/500 causes and debugging steps) and **log levels** → Phase 6
9. **Model serialization formats beyond pickle/joblib** (Keras, TensorFlow, PyTorch) and **model versioning/registries** (MLflow, DVC) → Phase 4
10. **Batch prediction rationale** (vectorized calls vs looping) → Phase 4
11. **Caching taxonomy** — client-side vs server-side vs CDN, eviction policies (LRU/LFU/FIFO), cache invalidation, Redis persistence (RDB/AOF), Redis beyond caching (sessions, rate limiting, pub/sub) → Phase 7
12. **Built-in FastAPI middlewares** (CORS, GZip, HTTPSRedirect) — the original only said "middleware" without naming the ones to check before writing custom code → Phase 5
13. **Specific benchmarking metrics** (latency, throughput, concurrency, error rate, resource usage) instead of "benchmark with Locust" as a vague step → Phase 8

---

## How to use this document

This is not a summary of what you learned — it's a **build order**. Every new project starts at Phase 0 and moves down. Each phase has a checklist; don't move to the next phase until the current one is checked off. The goal is that no project ships with a concept "skipped because I forgot it existed."

---

## 0. Standard Project Structure (use this for every project)

Create this skeleton before writing any logic. It's the structure your Capstone project used and it scales to any FastAPI + ML service:

```
project-folder/
├── app/
│   ├── __init__.py
│   ├── main.py                    # sets up routes, middleware, monitoring
│   ├── api/
│   │   ├── routes_predict.py      # /predict route
│   │   └── routes_auth.py         # /login route (JWT)
│   ├── core/
│   │   ├── config.py              # env vars & app-wide settings (pydantic-settings)
│   │   ├── security.py            # JWT creation/verification
│   │   ├── dependencies.py        # DI for API key / JWT validation
│   │   └── exceptions.py          # custom exception handlers
│   ├── services/
│   │   └── model_service.py       # loads ML model, predicts (+ Redis caching)
│   ├── middleware/
│   │   └── logging_middleware.py  # logs requests/responses
│   ├── cache/
│   │   └── redis_cache.py
│   ├── models.joblib               # serialized ML model
│   └── utils/
│       └── logger.py
├── notebooks/                     # experimentation
├── data/
├── training/
│   ├── __init__.py
│   ├── train_utils.py
│   └── train_model.py
├── tests/                         # unit + integration tests
├── requirements.txt
├── Dockerfile
├── docker-compose.yml             # FastAPI + Redis + Prometheus + Grafana
├── prometheus.yml
├── render.yaml                    # or your deployment platform's config
├── .env
└── README.md
```

---

## Phase 1 — Setup (before any code)

- [ ] Create GitHub repo → `git init` locally → connect remote → initial commit
- [ ] Create virtual environment, add `requirements.txt`
- [ ] Confirm Docker is installed (you'll containerize this eventually — plan for it from day 1)
- [ ] Write the README skeleton (project overview, setup, usage) — fill in as you go, not at the end
- [ ] Decide the API's purpose and its main resource(s) — sketch endpoints before coding (this maps to REST principles: nouns as resources, HTTP verbs as actions)
- [ ] **[Added] Deliberately choose the API protocol/style** — don't default to REST out of habit:
  - **REST** — default choice for most web/mobile/public APIs (stateless, HTTP verbs, resource URLs)
  - **GraphQL** — when clients need to query flexible/nested data shapes and over/under-fetching is a real problem
  - **gRPC** — for high-performance service-to-service calls (Protobuf, HTTP/2, streaming)
  - **WebSocket** — for real-time, low-latency, bidirectional use cases (chat, live dashboards, live predictions)
  - **SOAP** — only if integrating with legacy enterprise systems that require it
- [ ] **[Added] Plan the API lifecycle up front**, not just the first release:
  - [ ] Versioning strategy decided before the first public endpoint ships (e.g., `/v1/...`)
  - [ ] Design docs/contract drafted (Postman, SwaggerHub, or FastAPI's auto OpenAPI docs)
  - [ ] A rough plan for deprecation/retirement communication if this API will have external consumers
  - [ ] If deploying behind a gateway (Kong, AWS API Gateway, Apigee), decide that now — it affects routing, caching, and load-balancing design

---

## Phase 2 — Core API Design

- [ ] Confirm you're following REST conventions: correct HTTP methods (GET/POST/PUT/DELETE) and status codes for each action
- [ ] Design request/response as Pydantic schemas **first**, before writing route logic
- [ ] **[Added]** Use `Field` (not just bare types) for validation metadata — `StrictInt`, `StrictFloat`, min/max, regex, defaults — and `Optional` for non-required fields
- [ ] Implement basic CRUD endpoints
- [ ] Add input validation and typed responses — let Pydantic reject bad input instead of hand-rolled checks; return custom errors via `HTTPException` with the right status code
- [ ] **[Corrected] Decide sync vs async per route based on what the route actually does, not a blanket rule:**
  - Use `async def` when the route does I/O-bound work with async-capable libraries — HTTP calls (`httpx`), async DB drivers (`asyncpg`)
  - Use plain `def` when the route is **CPU-bound** (this includes most ML inference) or calls a **blocking** library (`requests`, `psycopg2`) — FastAPI runs these in a threadpool automatically, so forcing `async def` around blocking/CPU-heavy code actually blocks the event loop and hurts concurrency instead of helping it
- [ ] **[Added]** Add rate limiting / quotas if the API is public-facing — track and expose `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After` headers (Redis is a natural fit for the counters — see Phase 7)

---

## Phase 3 — Database Layer

- [ ] Set up SQLAlchemy: `database.py` (engine/session), `models.py` (ORM models), `schemas.py` (Pydantic), `crud.py` (DB operations), wired into `main.py`
- [ ] Keep DB session handling as a dependency (`Depends`), not global state
- [ ] Separate ORM models (`models.py`) from API schemas (`schemas.py`) — never return ORM objects directly from routes

---

## Phase 4 — ML Model Integration

- [ ] Train and serialize the model — pick the right format for the model type, not just pickle by default:
  - **Pickle / Joblib** — sklearn and general Python objects (joblib preferred for large numpy-heavy models)
  - **Keras (`.h5`/`.keras`)** or **TensorFlow SavedModel** — TF/Keras models
  - **PyTorch (`.pt`/`.pth`)** — PyTorch models
- [ ] Design explicit input/output Pydantic schemas for the model — don't accept raw dicts
- [ ] Load the model once at startup (not per-request) inside `model_service.py`
- [ ] Implement the single-prediction endpoint
- [ ] Implement a batch-prediction endpoint if the use case has bulk input — **[Added]** accept a *list* of inputs and run one vectorized `.predict()` call over the batch rather than looping and calling `.predict()` per item; this is significantly faster (optimized linear algebra, less I/O overhead, parallelized execution)
- [ ] Keep training code (`training/train_model.py`, `train_utils.py`) separate from serving code
- [ ] **[Added]** If this project will retrain/iterate over time, plan for model versioning from the start — a model registry (MLflow, DVC, or even a simple naming/versioning convention) so you can track, compare, and roll back model versions instead of silently overwriting `model.joblib`

---

## Phase 5 — Advanced FastAPI Concepts

- [ ] **Middleware** — check built-in options before writing custom ones:
  - **[Added]** `CORSMiddleware` — configure `allow_origins`, `allow_credentials`, `allow_methods`, `allow_headers` explicitly (never wildcard in production)
  - **[Added]** `GZipMiddleware` — compress responses for faster transfer
  - **[Added]** `HTTPSRedirectMiddleware` — force HTTPS
  - Only write a **custom middleware** (class with a `dispatch` method) for logging, timing, or logic the built-ins don't cover
- [ ] **Dependency Injection**: use `Depends` for DB connections, config, current-user/auth, and background task setup — don't instantiate these inline in route functions
- [ ] **Auth** — pick what the project actually needs, not just JWT by default:
  - [ ] **API Keys** — simplest option, fine for internal/public APIs without per-user login; via header (`api-key` header + `curl -H`) and/or `.env` + `pydantic-settings` `BaseSettings`
  - [ ] **JWT** — for stateless user auth: `/token` issues a JWT after verifying hashed password (bcrypt via passlib) → protected routes use `Depends(oauth2_scheme)` → verify + decode token → extract user
  - [ ] **[Added] OAuth 2.0 / OIDC** — when the app needs third-party login (Google/GitHub sign-in) or needs to delegate access without sharing credentials; OIDC adds identity/authentication on top of OAuth's authorization
  - [ ] **[Added] Bearer tokens** — the transport mechanism for OAuth/JWT tokens in the `Authorization` header; make sure it's validated on every protected route
  - [ ] **[Added] Refresh tokens** — issue alongside short-lived access tokens so users aren't forced to re-login constantly, without keeping access tokens long-lived
  - [ ] **[Added] MFA (multi-factor authentication)** — consider for anything handling sensitive data or admin access
- [ ] **Config management**: all secrets and settings loaded via `.env` + `core/config.py`, never hardcoded

**Security best-practices checklist (don't skip these — they were called out explicitly):**
- [ ] HTTPS in production
- [ ] JWT secrets / API keys in `.env` or a secret vault — never committed to git
- [ ] CORS configured properly (not wide open in production)
- [ ] CSRF protections where relevant
- [ ] Passwords hashed with bcrypt (or Argon2) — never stored/logged in plain text
- [ ] Token expiration set, with refresh tokens for renewal
- [ ] Role-Based Access Control (RBAC) if the project has multiple user roles
- [ ] **[Added]** Rate limiting in place for auth endpoints specifically (login/token endpoints are brute-force targets)
- [ ] **[Added]** Generic error messages on failed auth attempts (don't reveal "user not found" vs "wrong password" — that leaks account existence)
- [ ] **[Added]** Auth/access logs reviewed periodically for suspicious activity

---

## Phase 6 — Testing & Debugging

- [ ] Write tests early, not after the app is "done" — and cover all three layers, not just two:
  - **Unit tests** — single function/method, no external deps (business logic, Pydantic validators); fast, run with `pytest tests/`
  - **Integration tests** — multiple units together (API + DB, API + ML model, JWT across endpoints); uses test/in-memory DB
  - **[Added] End-to-End (E2E) tests** — simulate real user flows (login → predict → logout) as a black box; run pre-deployment to validate the whole system and deployment config, not just individual pieces
- [ ] Mock the ML model in tests (`unittest.mock.patch` on `.predict()`) — don't load the real model file in every test run; it's slow, resource-heavy, and irrelevant to testing API logic
- [ ] Add structured logging (not just `print`) — **[Added]** use proper log levels so logs are actually filterable/useful:
  - `DEBUG` (low-level detail) → `INFO` (routine, e.g. successful requests) → `WARNING` (unexpected but non-fatal) → `ERROR` (serious problem) → `CRITICAL` (app-terminating)
- [ ] Add centralized exception handling (`core/exceptions.py`) so errors return consistent, clean responses instead of raw stack traces
- [ ] Sanity-check the API manually with `curl` for each endpoint before considering it done (`-X` for method, `-H` for headers, `-d` for body)
- [ ] **[Added]** Run the dev server with `uvicorn main:app --reload --debug` for live reload and verbose stack traces — **remove `--debug` before production**, it leaks internals
- [ ] **[Added] Know this error catalog cold** — it's the fastest way to triage a broken endpoint:

  | Status | Meaning | Common cause | First thing to check |
  |---|---|---|---|
  | 401 Unauthorized | Auth failed | Missing/expired token, wrong API key, malformed `Authorization` header | Is the token valid and formatted correctly? |
  | 404 Not Found | Resource/route doesn't exist | Typo'd URL, route not registered | Recheck the path and method in the router |
  | 422 Unprocessable Entity | Body doesn't match schema | Missing required field, wrong type, failed Pydantic validation | Compare payload against the schema; test with curl/Postman |
  | 500 Internal Server Error | Unhandled exception server-side | Bug in code, DB connection issue, model not loaded | Check server logs / traceback; confirm dependencies are loaded before requests are served |

---

## Phase 7 — Performance: Caching

- [ ] Identify what's expensive: ML predictions, DB queries, external API calls — these are your caching candidates
- [ ] **[Added]** Decide *where* to cache, not just that you will:
  - **Client-side** — browser/HTTP `Cache-Control` headers, for static assets
  - **Server-side** — Redis/Memcached/in-memory dict, for computed results (this is what most of this phase covers)
  - **CDN** — for static content served close to users geographically
- [ ] Set up Redis (`docker run -d -p 6379:6379 redis`, then `redis-py` or `redis[async]` client)
- [ ] Cache ML prediction results (`app/cache/redis_cache.py` used from `model_service.py`)
- [ ] Cache repeated DB query results where it makes sense
- [ ] Cache external API calls if the project makes any
- [ ] Set sensible TTLs — don't cache forever by default
- [ ] **[Added]** Choose an eviction policy consciously if memory is a concern — LRU (Least Recently Used), LFU (Least Frequently Used), or FIFO — and have a plan for **cache invalidation** when the underlying data changes (this is usually the hardest part of caching, not the caching itself)
- [ ] **[Added]** Beyond caching, Redis is also useful for: session storage, rate-limiting counters, and pub/sub messaging — worth knowing if the project needs any of those, so you don't reach for a second tool unnecessarily
- [ ] **[Added]** If persistence matters (cache surviving a restart), know Redis supports RDB (periodic snapshots) and AOF (write-ahead log) — decide if either is needed or if a cold cache on restart is fine

---

## Phase 8 — Profiling & Benchmarking

- [ ] Profile before optimizing — use `time`, then `cProfile`, then `line_profiler` if you need line-level detail. Don't guess where the bottleneck is.
- [ ] Benchmark the API under load with Locust before calling performance "done"
- [ ] **[Added]** Track these metrics specifically, not just "is it fast":
  - **Latency** — response time per request (watch tail latency, not just average)
  - **Throughput** — requests handled per second
  - **Concurrency handling** — performance under many simultaneous requests (this is where async vs sync choices from Phase 2 actually show up)
  - **Error rate** — % of requests returning 4xx/5xx under load
  - **Resource usage** — CPU/RAM/disk I/O during load (informs autoscaling and cloud cost)
- [ ] Record baseline metrics so future changes can be compared against something, and so you can validate against any SLA (e.g., "p95 latency under 200ms") before going live

---

## Phase 9 — Monitoring & Containerization

- [ ] Instrument the app with Prometheus (FastAPI Instrumentator) → exposes `/metrics`
- [ ] Write `prometheus.yml` to scrape the app
- [ ] Write a `Dockerfile` for the FastAPI app
- [ ] Write `docker-compose.yml` to orchestrate FastAPI + Redis + Prometheus + Grafana together
- [ ] Bring the stack up with `docker-compose up --build` and verify:
  - [ ] `http://localhost:8000/` — app is up
  - [ ] `http://localhost:8000/metrics` — metrics exposed
  - [ ] `http://localhost:9090` — Prometheus UI, query `http_requests_total`
  - [ ] `http://localhost:3000` — Grafana (default admin/admin), add Prometheus as a data source (`http://prometheus:9090`)
  - [ ] Build at least one Grafana dashboard using `http_server_requests_total`, `http_request_duration_seconds_bucket`, `http_request_duration_seconds_sum`

---

## Phase 10 — Deployment

- [ ] Provision managed Redis (e.g., Redis Cloud) if not self-hosting → update `redis_cache.py` with the connection URL
- [ ] Write the deployment config for your target platform (e.g., `render.yaml`)
- [ ] Connect the GitHub repo to the platform and deploy
- [ ] Confirm environment variables/secrets are set on the platform, not just locally in `.env`
- [ ] Smoke-test the deployed endpoints the same way you tested locally

---

## Final "Definition of Done" — run this before calling a project production-grade

- [ ] Folder structure matches the standard layout above
- [ ] All secrets in `.env` / vault, nothing hardcoded or committed
- [ ] Auth implemented and tested (JWT and/or API key)
- [ ] Tests exist and pass, ML model is mocked in tests
- [ ] Logging + centralized exception handling in place
- [ ] Caching applied to at least the expensive paths (model inference, DB, external calls)
- [ ] Profiled once, benchmarked once — numbers recorded somewhere
- [ ] Prometheus + Grafana wired up and showing real metrics
- [ ] Dockerized and runnable via `docker-compose up --build`
- [ ] Deployed, and deployed endpoints manually verified
- [ ] README is actually usable by someone who isn't you

---

*Source: built from your FastAPI-for-ML course notes (Intro to APIs → Capstone Project). Use this as the checklist for every new project so each concept gets deliberately implemented rather than left as "something I learned once."*
