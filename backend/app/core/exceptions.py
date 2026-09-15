"""Centralized exception types and handlers.

Failure taxonomy (per CLAUDE.md): classification / extraction / provider /
citation-verification / data-quality. Each pipeline stage raises one of these instead of
letting a raw exception or provider error reach the API layer. Extended in Phase 6 with
the full guardrail/auth failure paths; the base taxonomy is established here in Phase 0
so later phases have a consistent type to raise into.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class TenderPlatformError(Exception):
    """Base class for all typed application errors."""

    status_code: int = 500
    user_message: str = "Something went wrong. Please try again."

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.user_message
        super().__init__(self.detail)


class ClassificationError(TenderPlatformError):
    status_code = 500
    user_message = "Could not classify one or more pages in this document."


class ExtractionError(TenderPlatformError):
    status_code = 500
    user_message = "Could not extract text from one or more pages in this document."


class ProviderError(TenderPlatformError):
    status_code = 502
    user_message = "An upstream AI provider is unavailable. Please try again shortly."


class CitationVerificationError(TenderPlatformError):
    status_code = 500
    user_message = "Could not verify a citation against the source document."


class DataQualityError(TenderPlatformError):
    status_code = 422
    user_message = "The input data does not meet the requirements for analysis."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(TenderPlatformError)
    async def handle_platform_error(
        request: Request, exc: TenderPlatformError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "message": exc.detail},
        )
