from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# connect_args bound two previously-unbounded failure modes (CLAUDE.md hard rule 10 —
# every external call needs a timeout; this one had none): this project's real
# Postgres is reached over a Tailscale VPN link to a colleague's own machine (docs/
# DECISIONS.md #21), not a managed/local instance, so a dropped tunnel or a stuck
# query could previously hang a connection — and, under Celery's --pool=solo (one
# task at a time, synchronous), freeze that entire worker indefinitely with no error,
# no timeout, and no way to even tell it apart from a crashed process from the
# outside. connect_timeout bounds how long establishing a new connection can take;
# the statement_timeout GUC (set via libpq's `options`, not a SQLAlchemy-level
# setting) bounds how long any single query can run once connected.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10, "options": "-c statement_timeout=120000"},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
