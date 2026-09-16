"""Centralized exception types and handlers.

Failure taxonomy (per CLAUDE.md): classification / extraction / provider /
citation-verification / data-quality / authentication / rate-limit. Each pipeline stage
raises one of these instead of letting a raw exception or provider error reach the API
layer. Phase 6 adds authentication/rate-limit to the base taxonomy established in
Phase 0, and the shared handler below now logs every error server-side (structured,
with the exception type and detail) before returning the user-facing message — the
Phase 6 gate requires "every failure type -> correct user message + internal log," and
doing it once here covers every TenderPlatformError raised anywhere in the app, rather
than requiring every call site to remember to log too.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class TenderPlatformError(Exception):
    """Base class for all typed application errors."""

    status_code: int = 500
    user_message: str = "Something went wrong. Please try again."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.user_message
        super().__init__(self.detail)


class ClassificationError(TenderPlatformError):
    """Currently unused by design, not an oversight: app.pipeline.classify.classify_page
    is a total function (every branch, including "no signal at all," returns a
    classification — never raises). Kept in the taxonomy for a future classification
    signal that genuinely can fail (e.g. an unreadable page)."""

    status_code = 500
    user_message = "Could not classify one or more pages in this document."


class ExtractionError(TenderPlatformError):
    status_code = 500
    user_message = "Could not extract text from one or more pages in this document."


class ProviderError(TenderPlatformError):
    status_code = 502
    user_message = "An upstream AI provider is unavailable. Please try again shortly."


class CitationVerificationError(TenderPlatformError):
    """Currently unused by design, not an oversight: app.pipeline.citation_verify
    deliberately models an unresolvable page_ref as data (`verified: false`, per
    docs/SPEC.md §7's "shown as unverified, never hidden" rule), not as an exception —
    a failed citation is an expected, displayable outcome, not a pipeline failure."""

    status_code = 500
    user_message = "Could not verify a citation against the source document."


class DataQualityError(TenderPlatformError):
    status_code = 422
    user_message = "The input data does not meet the requirements for analysis."


class AuthenticationError(TenderPlatformError):
    status_code = 401
    user_message = "Incorrect username or password."


class RateLimitError(TenderPlatformError):
    status_code = 429
    user_message = "Too many attempts. Please try again shortly."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TenderPlatformError)
    async def handle_platform_error(
        request: Request, exc: TenderPlatformError
    ) -> JSONResponse:
        logger.warning(
            "request.failed",
            path=request.url.path,
            error_type=exc.__class__.__name__,
            status_code=exc.status_code,
            detail=exc.detail,
        )
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "message": exc.detail},
            headers=headers,
        )
