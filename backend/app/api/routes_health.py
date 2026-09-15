from fastapi import APIRouter, Depends
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness — the process is up. Does not check dependencies."""
    return {"status": "ok"}


@router.get("/ready")
def ready(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness — the app can actually serve traffic (DB + Redis reachable)."""
    db.execute(text("SELECT 1"))

    redis_client = Redis.from_url(settings.redis_url, socket_connect_timeout=2)
    try:
        redis_client.ping()
    except RedisError as exc:
        raise RuntimeError("Redis is not reachable") from exc

    return {"status": "ready"}
