from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "tender_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

# Task modules are registered here as each pipeline phase adds them
# (tasks_ingest, tasks_chunk, tasks_map, tasks_reduce, tasks_pipeline — Phases 2-5).
celery_app.autodiscover_tasks(["app.workers"])
