# Runbook — Tender AI Platform

> Placeholder created in Phase 0. Filled in during Phase 8 once the pipeline, guardrails,
> and monitoring exist to document real failure modes against.

## To be filled in Phase 8
- [ ] Known failure cases per pipeline stage (classification / extraction / provider /
      citation-verification / data-quality — see the failure taxonomy in `CLAUDE.md`)
- [ ] What to do when a Celery task is stuck / a chunk repeatedly fails
- [ ] What to do when a free-tier provider quota is exhausted mid-pipeline
- [ ] How to re-run analysis for a single document without reprocessing pages
- [ ] Data export / deletion procedure (shallow exit-strategy scope per Tier 2)
- [ ] On-call ownership per subsystem (retrieval N/A here; ingestion, pipeline, API, infra)
