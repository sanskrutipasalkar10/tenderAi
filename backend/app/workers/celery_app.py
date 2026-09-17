"""Celery app config. Queue split and concurrency are based on real measured
behavior (docs/DECISIONS.md #47), not guesswork:

- "llm" queue: every task that calls Ollama (map pass, reduce pass, ingestion's
  vision extraction) — tasks_map.py, tasks_reduce.py, tasks_ingest.py.
- "default" queue: everything else (chunk planning) — cheap, no LLM call, must never
  queue behind a slow LLM task waiting for a shared worker slot.

Run two separate worker pools against these queues (see docker-compose.yml) rather
than one pool for everything: a single pool sized for LLM-task concurrency would
needlessly throttle chunk-building, and a single pool sized for chunk-building's cheap
concurrency would over-subscribe Ollama Cloud/hit its real per-request latency
degradation under load (see #47).
"""

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
    task_default_queue="default",
    # Don't ack a task until it actually finishes — an LLM-calling task can run for
    # minutes (docs/DECISIONS.md #36); acking early (Celery's default) would mean a
    # worker crash mid-call silently loses the task instead of redelivering it.
    task_acks_late=True,
    # Default prefetch (4) would let one worker grab 4 long LLM tasks up front before
    # finishing any of them, starving other workers. 1 means a worker only picks up
    # its next task once free.
    worker_prefetch_multiplier=1,
    # Emits task-sent/-started/-succeeded/-failed events onto the broker (docs/
    # DECISIONS.md #54) — consumed by the celery-exporter sidecar in docker-compose.yml
    # to produce real per-queue/per-task Prometheus metrics, without any custom
    # multiprocess-safe metrics code in the worker processes themselves.
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Per-chunk/per-module time limits — set on tasks_map.py/tasks_reduce.py individually,
# NOT here as a global default. Deliberately NOT applied to tasks_ingest.py: that
# task still processes a whole document (every page, including every vision LLM call)
# in one task, so its legitimate worst-case runtime scales with document size and a
# fixed ceiling would kill real large-document ingestion. Fanning ingestion out to one
# task per page (matching map_pass's per-chunk design) would remove the need for this
# distinction, but is a bigger architectural change than this phase's scope — noted
# here, not silently done.
LLM_TASK_SOFT_TIME_LIMIT = 600
LLM_TASK_TIME_LIMIT = 660

# Task modules are registered here as each pipeline phase adds them
# (tasks_ingest, tasks_chunk, tasks_map, tasks_reduce, tasks_pipeline — Phases 2-5).
celery_app.autodiscover_tasks(["app.workers"])
