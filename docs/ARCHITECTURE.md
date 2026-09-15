# Architecture — Tender AI Platform

> Placeholder created in Phase 0. Filled in during Phase 8 (Observability & Ship) once
> the full pipeline exists to diagram accurately. See `docs/SPEC.md` §2.1/§10 and the
> implementation plan for the architecture decided so far: a Celery-orchestrated
> map-reduce pipeline (classify → extract → dedupe → chunk → map → reduce → serve), not
> an agent and not RAG.

## To be filled in Phase 8
- [ ] Pipeline diagram (ingestion → storage → chunking/two-pass AI → serving)
- [ ] Data flow through the three DB layers (raw / structured / analysis)
- [ ] Sequence diagram: upload → Celery chain/chord → document_analysis rows
- [ ] Deployment diagram (docker-compose services and how they connect)
