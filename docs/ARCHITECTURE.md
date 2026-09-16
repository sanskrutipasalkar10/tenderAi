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

---

## Bronze/Silver/Gold export layer (docs/DECISIONS.md #17)

A colleague independently designed a 4-table schema for the company/tender data
(`company_master_profile`, `tender_bronze_raw`, `tender_silver_extracted`,
`tender_gold_analysis`), presumably for downstream reporting/BI consumption. It's
chunk-level (a `page_range` string like `"Pages 1-20"`) rather than page-level, so it
can't support exact-page citation on its own — the spec's core "every risk flag citing a
real page" requirement needs our page-level schema (§3.1 of the spec) as the system of
record. Per the user's decision, **our schema stays canonical**; the colleague's 4 tables
are treated as a **derived export/reporting view**, synced from it, not an alternative
source of truth. Both schemas' DDL are applied verbatim — neither is redesigned to
accommodate the other.

**This export/sync logic is Phase 5+ work** (it needs `document_analysis` rows to exist)
— not built yet. Recorded here now, while the mapping is fresh, so Phase 5 implements it
against a plan instead of improvising one.

### Table mapping

| Colleague's table | Derived from (our schema) | Mapping notes |
|---|---|---|
| `company_master_profile` | `company_profiles` | `company_id` (SERIAL) has no natural counterpart to our UUID `id` — on sync, look up an existing export row by a hidden `profile_data._source_company_profile_id` field (set to our UUID) before inserting, so re-syncs upsert rather than duplicate. `profile_data` = the full `company_profiles` row serialized as one JSON object (turnover, certifications, past_projects, etc. all nested, matching their "unified JSON representation" intent). |
| `tender_bronze_raw` | `chunks` (one row per chunk, not per page) | `tender_id` = `str(documents.id)`. `chunk_sequence` = 1-indexed order by `chunks.start_page`. `page_range` = `f"Pages {start_page}-{end_page}"` — this is where citation precision is lost in the export view; internal citations still resolve against `pages.page_number`, never against this string. `raw_text` = concatenation of the constituent pages' `raw_text`, in page order. |
| `tender_silver_extracted` | `chunk_extractions` | `bronze_chunk_id` = the `tender_bronze_raw` row created for the same `chunk_id`. `extracted_requirements` = `chunk_extractions.structured_json` as-is. |
| `tender_gold_analysis` | `document_analysis` (all 3 module rows, merged into one) | `tender_id` = `str(documents.id)` (`UNIQUE`, matching our own `UNIQUE(document_id, module)` upsert semantics — one gold row per tender). `go_nogo_status`/`go_nogo_score` = the `go_no_go` module's `decision`/`score`. `match_report` = `{"criteria_matches": ..., "gaps": ..., "synopsis": <the synopsis module's full result>}` — **the colleague's schema has no dedicated synopsis field**; nesting it inside `match_report` is a deliberate compatibility choice so their DDL isn't altered unilaterally. Flag to the colleague: a dedicated `synopsis JSONB` column would be cleaner if they're open to a small migration on their side. `document_roadmap` = the `go_no_go` module's `next_steps`. `risk_matrix` = the `risk_finder` module's full result. |

### What does NOT get exported
`pages`, `extracted_tables`, and `boilerplate_cache` have no equivalent in the colleague's
schema and aren't exported — they're purely internal to how we guarantee exact-page
citation and cross-document dedupe, which the export layer's consumers don't need.
