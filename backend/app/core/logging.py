import logging
import sys

import structlog

from app.core.config import settings


def configure_logging() -> None:
    # Real content logged by pipeline stages (LLM output, tender clause text) routinely
    # contains non-ASCII characters (typographic punctuation, currency symbols) — on
    # Windows, stdout defaults to the console's codepage (cp1252), not UTF-8, and a
    # structlog PrintLogger writing one of those characters raises UnicodeEncodeError,
    # crashing whatever pipeline call was mid-log. Reconfiguring stdout to UTF-8 with a
    # safe fallback makes logging itself unable to crash a call (docs/DECISIONS.md #41).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
