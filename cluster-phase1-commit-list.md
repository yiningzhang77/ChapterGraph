# cluster-phase1-commit-list.md

Date: 2026-03-09  
Goal: Implement `cluster-phase1-plan.md` with the new enrichment shape `sections[].bullets[]`, `chapter_index_text` retrieval, and nullable `source_refs`.

## Progress Snapshot

- Planned commits: `01` to `10`
- Completed: `01` to `10`
- In progress: none

---

## [x] Commit 01 - `refactor(ingestion): emit structured sections[].bullets[] and remove signals`

Purpose:
- Make `sections[].bullets[]` the canonical enrichment structure at source.

Changes:
- update `feature_achievement/ingestion.py`
- implement deterministic IDs:
  - `section_id = {chapter_id}::s{n}`
  - `bullet_id = {section_id}::b{n}`
- emit per section:
  - `title_raw`, `title_norm`, `order`, `bullets[]`
- emit per bullet:
  - `text_raw`, `text_norm`, `order`, `source_refs` (`null`)
- remove `signals` from emitted chapter payload

Verify:
- run parser on sample books and inspect generated chapter objects
- ensure `sections` contains objects only (no string sections)
- ensure `signals` key is absent

---

## [x] Commit 02 - `feat(enrichment): generate deterministic chapter_index_text from section/bullet norms`

Purpose:
- Formalize coarse retrieval text into `chapter_index_text`.

Changes:
- update `feature_achievement/enrichment.py`
- add normalization utility for `*_norm`
- build `chapter_index_text` with deterministic token order:
  - `book:... chapter:... title:... section:... bullet:...`
- append `bullet:none` when section has no bullets
- optional transition: keep `chapter_text = chapter_index_text`

Verify:
- inspect generated `chapter_index_text` for several chapters
- repeat generation twice and confirm identical output

---

## [x] Commit 03 - `chore(output): regenerate output/*_enriched.json to v2 shape`

Purpose:
- Ensure checked runtime artifacts match new contract.

Changes:
- regenerate all `output/*_enriched.json`
- ensure every chapter follows `sections[].bullets[]`
- ensure no `signals` appears

Verify:
- run schema check script (added in Commit 05)
- manually inspect at least 3 files:
  - `output/spring-in-action_enriched.json`
  - `output/springboot-in-action_enriched.json`
  - `output/spring-start-here_enriched.json`

---

## [x] Commit 04 - `feat(db): add chapter_index_text and remove signals from EnrichedChapter model`

Purpose:
- Align DB schema with v2 enrichment contract.

Changes:
- update `feature_achievement/db/models.py`
  - add `chapter_index_text: str`
  - remove `signals` field from model
- add migration script:
  - `feature_achievement/scripts/migrate_enriched_v2_schema.py`
  - add `chapter_index_text` column
  - drop `signals` column (or stop using and schedule drop if needed)

Verify:
- migration runs successfully
- DB table `enriched_chapter` has `chapter_index_text`
- `signals` is not used by runtime code

---

## [x] Commit 05 - `feat(script): add enriched v2 transformer and schema validator`

Purpose:
- Provide one-shot backfill and enforce shape correctness.

Changes:
- add `feature_achievement/scripts/migrate_enriched_shape_v2.py`
  - transform legacy rows/files into v2 objects
  - fill nullable `source_refs`
  - compute `chapter_index_text`
- add `feature_achievement/scripts/validate_enriched_v2.py`
  - fail if any chapter violates v2 schema

Verify:
- run migration script end-to-end
- validator reports pass on all `output/*_enriched.json`

---

## [x] Commit 06 - `refactor(import): persist enriched v2 payload into DB`

Purpose:
- Ensure import path writes new shape correctly.

Changes:
- update `feature_achievement/db/crud.py`
  - `persist_enriched_chapters()` writes `chapter_index_text` and structured `sections`
- update `feature_achievement/scripts/import_enriched_chapters.py`
  - enforce v2 schema validation before import
- remove any remaining `signals` references

Verify:
- run import script with overwrite
- spot-check DB rows for structured `sections` and non-empty `chapter_index_text`

---

## [x] Commit 07 - `feat(retrieval): switch term seed search to chapter_index_text`

Purpose:
- Make `/ask` coarse recall use the new index field.

Changes:
- update `feature_achievement/db/ask_queries.py`
  - `search_term_seed_ids_ilike()` targets `chapter_index_text`
- update `feature_achievement/ask/cluster_builder.py` where needed
- keep existing 404/409/422 behavior unchanged

Verify:
- term-mode `/ask` still returns non-empty cluster on known terms
- chapter-mode `/ask` unaffected

---

## [x] Commit 08 - `feat(localize): add section/bullet evidence localization in ask path`

Purpose:
- Implement hierarchical recall after chapter hit.

Changes:
- update `feature_achievement/ask/cluster_builder.py`
  - add deterministic in-memory localizers:
    - `rank_sections_local(...)`
    - `rank_bullets_local(...)`
- update `feature_achievement/api/schemas/ask.py`
  - add optional evidence response schema fields
- update `feature_achievement/api/routers/ask.py`
  - return `evidence.sections[]` and `evidence.bullets[]`
  - preserve nullable `source_refs`

Verify:
- `/ask` response includes evidence block
- every bullet in response contains `source_refs` key (nullable accepted)

---

## [x] Commit 09 - `test(cluster-v2): add schema/retrieval/localization coverage`

Purpose:
- Lock in contract and prevent regressions.

Changes:
- add `tests/test_enriched_v2_shape.py`
- add `tests/test_chapter_index_text_builder.py`
- extend `tests/test_ask_cluster_builder.py`
- extend `tests/test_ask_api.py`

Coverage:
- `sections[].bullets[]` shape validity
- no `signals` usage
- term search via `chapter_index_text`
- section/bullet ranking determinism
- nullable `source_refs` behavior

Verify:
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 10 - `chore(smoke-docs): update smoke scripts and docs for v2 enrichment`

Purpose:
- Close delivery loop for developers/operators.

Changes:
- update `feature_achievement/scripts/smoke_ask_cluster.py`
- update `feature_achievement/scripts/smoke_ask.py`
- add optional smoke script:
  - `feature_achievement/scripts/smoke_enriched_v2.py`
- update docs:
  - `cluster-phase1-plan.md` status checkboxes if needed
  - `README.md` enrichment v2 runbook

Verify:
- smoke scripts pass on current DB
- docs commands are executable as written

---

## Continuous Checks (each commit)

- Backend tests: `$env:PYTHONPATH='.'; pytest -q`
- Ask smoke: `python -m feature_achievement.scripts.smoke_ask_cluster`
- Full smoke: `python -m feature_achievement.scripts.smoke_ask`
- Enrichment shape validation: `python -m feature_achievement.scripts.validate_enriched_v2`
