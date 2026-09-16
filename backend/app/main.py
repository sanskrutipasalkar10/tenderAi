from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import routes_analysis, routes_auth, routes_health, routes_ingest, routes_status
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

register_exception_handlers(app)
app.include_router(routes_health.router)
app.include_router(routes_auth.router)

# Every document/analysis route requires a valid JWT (docs/DECISIONS.md #44) — /health
# and /token are the only unauthenticated routes.
_auth_dependency = [Depends(get_current_user)]
app.include_router(routes_ingest.router, dependencies=_auth_dependency)
app.include_router(routes_status.router, dependencies=_auth_dependency)
app.include_router(routes_analysis.router, dependencies=_auth_dependency)

Instrumentator().instrument(app).expose(app)
