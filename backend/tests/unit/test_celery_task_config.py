"""Verifies the queue/time-limit wiring on every Celery task (docs/DECISIONS.md #47) —
no broker needed, this just inspects each task's own decorator-set attributes. Without
this, an accidental removal of `queue="llm"` from a task decorator would silently put
an LLM-bound task back on the "default" queue (sized for cheap, fast work) and nothing
else would catch it.
"""

from app.workers.celery_app import LLM_TASK_SOFT_TIME_LIMIT, LLM_TASK_TIME_LIMIT, celery_app
from app.workers.tasks_chunk import build_chunks_task
from app.workers.tasks_ingest import ingest_document_task
from app.workers.tasks_map import map_pass_chunk_task
from app.workers.tasks_reduce import go_no_go_task, risk_finder_task, synopsis_task


def test_llm_calling_tasks_are_on_the_llm_queue() -> None:
    llm_tasks = (
        map_pass_chunk_task,
        go_no_go_task,
        synopsis_task,
        risk_finder_task,
        ingest_document_task,
    )
    for task in llm_tasks:
        assert task.queue == "llm", task.name


def test_chunk_building_is_on_the_default_queue() -> None:
    # No explicit `queue=` on the decorator at all -> Celery doesn't even set the
    # attribute; falls back to celery_app's task_default_queue="default" at dispatch time.
    assert getattr(build_chunks_task, "queue", None) is None


def test_per_chunk_and_per_module_tasks_have_a_bounded_time_limit() -> None:
    for task in (map_pass_chunk_task, go_no_go_task, synopsis_task, risk_finder_task):
        assert task.soft_time_limit == LLM_TASK_SOFT_TIME_LIMIT, task.name
        assert task.time_limit == LLM_TASK_TIME_LIMIT, task.name


def test_ingestion_task_has_no_fixed_time_limit() -> None:
    # Deliberately unbounded (celery_app.py's docstring) — a whole document's worth of
    # pages/vision calls can legitimately exceed any single chunk/module's ceiling.
    assert ingest_document_task.soft_time_limit is None
    assert ingest_document_task.time_limit is None


def test_task_events_are_enabled_for_the_celery_exporter() -> None:
    # celery-exporter (docker-compose.yml, docs/DECISIONS.md #54) reads these events
    # off the broker to produce real Prometheus metrics — without this config, its
    # /metrics endpoint would just be permanently empty, silently.
    assert celery_app.conf.worker_send_task_events is True
    assert celery_app.conf.task_send_sent_event is True
