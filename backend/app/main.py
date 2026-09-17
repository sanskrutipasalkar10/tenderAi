from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import (
    routes_analysis,
    routes_auth,
    routes_company_profiles,
    routes_health,
    routes_ingest,
    routes_pages,
    routes_status,
)
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(
    title="Tender AI Platform",
    description=(
        "Reads Indian government tender PDFs and produces a Go/No-Go recommendation, "
        "a synopsis, and a page-cited risk list."
    ),
    version="0.1.0",
)

# The Next.js frontend (frontend/, docs/DECISIONS.md #56) runs on a different origin
# than this API — without this, every browser request from it is blocked by the
# browser itself (same-origin policy), before this app ever sees the request. Found
# by actually driving the frontend against this API in a real browser, not by
# inspection — see docs/DECISIONS.md #56.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(routes_health.router)
app.include_router(routes_auth.router)

# Every document/analysis route requires a valid JWT (docs/DECISIONS.md #44) — /health
# and /token are the only unauthenticated routes.
_auth_dependency = [Depends(get_current_user)]
app.include_router(routes_ingest.router, dependencies=_auth_dependency)
app.include_router(routes_status.router, dependencies=_auth_dependency)
app.include_router(routes_analysis.router, dependencies=_auth_dependency)
app.include_router(routes_pages.router, dependencies=_auth_dependency)
app.include_router(routes_company_profiles.router, dependencies=_auth_dependency)

Instrumentator().instrument(app).expose(app)
