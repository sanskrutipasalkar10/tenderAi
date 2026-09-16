from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import routes_health, routes_ingest, routes_status
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
app.include_router(routes_ingest.router)
app.include_router(routes_status.router)

Instrumentator().instrument(app).expose(app)
