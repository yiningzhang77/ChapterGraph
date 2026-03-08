# `/ask` Feasibility Research (Implementation-Oriented)

Date: 2026-03-07  
Repo: `c:\Users\hy\ChapterGraph`

## 1. Scope and Method

This report evaluates whether the full `/ask` feature from `plan.md` can be implemented on the current codebase, and what blocks or slows delivery.

I validated:

- Current API/DB/retrieval source code (`feature_achievement/api`, `db`, `retrieval`, `scripts`).
- Current test state (`tests/`).
- Live local DB shape/readiness (table counts, indices, sample query plans).
- Runtime behavior assumptions in `plan.md` against current implementation reality.

## 2. Current Reality Snapshot (Verified)

## 2.1 Existing backend contract

- API app mounts only `edges` router (`feature_achievement/api/main.py`).
- Existing endpoints: `/compute-edges`, `/edges`, `/graph`, `/runs` (`feature_achievement/api/routers/edges.py`).
- There is no `/ask` endpoint yet.

## 2.2 Data model state relevant to `/ask`

- `EnrichedChapter` exists with fields needed for cluster payload: `id`, `book_id`, `title`, `chapter_text`, `sections`, `signals`, `enrichment_version` (`feature_achievement/db/models.py`).
- `Edge` is run-scoped (`run_id`, `from_chapter`, `to_chapter`, `score`, `type`) and directional.
- `Run` stores `book_ids`, `enrichment_version`, scoring config.

## 2.3 Local DB readiness (current machine)

Observed counts:

- `run`: 4
- `edge`: 28
- `enriched_chapter`: 41
- `chapter`: 41
- `book`: 3

Observed enrichment version distribution:

- `enriched_chapter.enrichment_version = 'v1_test'` for all 41 rows.

Observed run versions:

- all runs currently store `enrichment_version = 'v1_bullets+sections'`.

This is a concrete integrity gap for version-scoped `/ask`.

## 2.4 Test and runtime status

- `pytest -q` fails by default due to import path (`ModuleNotFoundError: feature_achievement`).
- `PYTHONPATH=.` fixes it; then all tests pass (7 passed).
- Existing tests only cover `/compute-edges` request contract and basic API flow; no `/ask` coverage exists.

## 3. Feasibility Verdict

## 3.1 Overall

Implementing `/ask` on top of current codebase is feasible with low architectural risk.

- Deterministic cluster-building from DB is straightforward with current models.
- Graph expansion by run-scoped edges is already represented in schema.
- The main work is integration work: new router + cluster service + query helpers + constrained LLM adapter.

## 3.2 Delivery risk level

- Cluster-only `/ask` (no LLM): Low risk.
- Full `/ask` with constrained Qwen output: Medium risk (mainly adapter/config/runtime determinism concerns, not data modeling).

## 4. What You Can Reuse Directly

## 4.1 Reusable backend pieces

- DB session wiring (`feature_achievement/db/engine.py`).
- SQLModel entities for run/edge/chapter data (`feature_achievement/db/models.py`).
- Existing API routing patterns and response modeling style (`feature_achievement/api/routers/edges.py`).
- Existing run-scoped graph storage (`Edge.run_id`).

## 4.2 Reusable data assets

- `enriched_chapter` already stores cluster-grade content signals.
- `edge` table already stores relation weights and relation type (`tfidf` / `embedding`).

## 4.3 Reusable process pieces

- Existing import script for enriched payloads (`feature_achievement/scripts/import_enriched_chapters.py`).
- Existing run generation flow (`/compute-edges`) can continue to own edge construction.

## 5. Key Impediments (Severity + Impact + Fix)

## 5.1 Critical: run/enrichment version integrity is not enforced

Problem:

- `/compute-edges` writes `Run.enrichment_version` from request, but retrieval uses file-loaded data, not DB `EnrichedChapter`.
- Current DB already shows mismatch: runs are `v1_bullets+sections`, enriched chapters are `v1_test`.

Impact:

- A strict `/ask` filter by `(run_id, enrichment_version)` can return incomplete or empty clusters even when data exists.

Fix:

- In `/ask`, validate run existence and return explicit 409/422 when requested version does not match available enriched data.
- Optionally require `req.enrichment_version == run.enrichment_version` unless an override flag is provided.
- Medium-term: align `/compute-edges` source-of-truth with imported `enriched_chapter` rows or enforce synchronized import/versioning workflow.

## 5.2 High: no deterministic cluster-builder module exists yet

Problem:

- No current module assembles seeds -> hops -> chapter payload -> budgeted cluster JSON.

Impact:

- `/ask` would be implemented ad hoc inside route unless a dedicated service is added.

Fix:

- Add `feature_achievement/ask/cluster_builder.py` with pure deterministic functions and no LLM dependencies.

## 5.3 High: no LLM abstraction/config exists

Problem:

- No Qwen adapter, no prompt layer, no provider/env contract, no timeout/retry policy.

Impact:

- "Full `/ask`" blocks at inference integration point.

Fix:

- Add `feature_achievement/llm/qwen_client.py` plus `feature_achievement/llm/prompts.py`.
- Keep `/ask` operable with `llm_enabled=false` (cluster-only) to decouple data-path completion from model integration.

## 5.4 High: `Run` rows can exist with no usable edges

Problem:

- `/compute-edges` persists `Run` before validating requested books and before edge generation.
- This allows orphan or empty runs.

Impact:

- `/ask` can receive valid run_id that has zero edges; cluster expansion quality collapses.

Fix:

- `/ask` must validate edge count for run and degrade gracefully:
  - either return seed-only cluster with `meta.warnings`
  - or fail with explicit `422 run has no edges`.

## 5.5 Medium: index strategy is enough now, not enough later

Current:

- Single-column indexes exist (`edge.run_id`, `edge.from_chapter`, `edge.to_chapter`).
- Query plan for expansion currently uses `ix_edge_run_id` then filters/sorts.

Impact:

- Works at current scale (41 chapters), degrades with larger corpora/runs.

Fix:

- Add composite indexes:
  - `edge(run_id, from_chapter, score DESC)`
  - `edge(run_id, to_chapter, score DESC)` if reverse expansion is supported
  - `enriched_chapter(enrichment_version, book_id)` (if not already present consistently in model/migration path)

## 5.6 Medium: model/schema drift risk for indices

Problem:

- Local DB currently has `ix_enriched_chapter_enrichment_version`, but model does not explicitly set `index=True` for `enrichment_version`.

Impact:

- Fresh environments may miss expected index unless migration or manual index creation is repeated.

Fix:

- Add explicit index declaration in model or migration script; treat DB index setup as code, not local accident.

## 5.7 Medium: term retrieval quality is currently basic

Problem:

- MVP term search will rely on `ILIKE` over chapter text/title; no BM25, no trigram ranking, no stemming/synonyms.

Impact:

- Acceptable for initial deterministic flow, but recall/precision can be noisy.

Fix:

- Ship `ILIKE` first, then add pg_trgm-based ranking or lexical scorer if needed.

## 5.8 Medium: current app config is hard-coded

Problem:

- DB URL is hard-coded in `db/engine.py`; no runtime settings layer for LLM endpoint/api key/timeouts.

Impact:

- Harder to run `/ask` across environments and CI.

Fix:

- Add environment-driven settings for DB + LLM integration.

## 6. Implementation Blueprint (Concrete)

## 6.1 Module layout

Add:

- `feature_achievement/api/schemas/ask.py`
- `feature_achievement/api/routers/ask.py`
- `feature_achievement/ask/cluster_builder.py`
- `feature_achievement/db/ask_queries.py` (or extend `crud.py`)
- `feature_achievement/llm/prompts.py`
- `feature_achievement/llm/qwen_client.py`

Update:

- `feature_achievement/api/main.py` to include `ask.router`.

## 6.2 Request/response contract (recommended)

Use the contract in `plan.md` with these implementation notes:

- Map `chapter_id` externally to DB `EnrichedChapter.id`.
- Add `strict_version_match: bool = True` to make mismatch behavior explicit.
- Add `llm_timeout_ms` and `max_cluster_chapters` to avoid unbounded runtime/payload.

## 6.3 Deterministic cluster algorithm

Suggested deterministic steps:

1. Validate run exists.
2. Validate run has edges (or allow seed-only fallback).
3. Resolve seeds:
   - `query_type=term`: search `enriched_chapter` by `ILIKE` on `chapter_text` OR `title`, filtered by `enrichment_version`.
   - `query_type=chapter`: exact id lookup first, then fallback title match.
4. Expand by edges for given `run_id`:
   - hop 1 from seed ids; optional hop 2 from hop-1 frontier.
   - filter by `score >= min_edge_score`.
   - budget by `neighbor_top_k`.
5. Fetch all involved enriched chapters with version filter.
6. Assemble cluster JSON with field whitelist and truncation budgets.

## 6.4 Query helpers to add

Required helper functions:

- `get_run(session, run_id)`
- `count_run_edges(session, run_id)`
- `search_term_seeds(session, term, enrichment_version, limit)`
- `get_edges_from(session, run_id, source_ids, min_score, limit)`
- `get_edges_to(session, run_id, target_ids, min_score, limit)` (if reverse expansion enabled)
- `get_enriched_by_ids(session, chapter_ids, enrichment_version)`

## 6.5 Cluster schema (recommended minimal stable format)

```json
{
  "schema_version": "cluster.v1",
  "query": "actuator",
  "query_type": "term",
  "run_id": 5,
  "enrichment_version": "v1_test",
  "seed": {
    "seed_chapter_ids": ["spring-in-action::ch15", "springboot-in-action::ch7"],
    "seed_reason": "term_match"
  },
  "chapters": [],
  "edges": [],
  "constraints": {
    "max_hops": 1,
    "seed_top_k": 5,
    "neighbor_top_k": 20,
    "min_edge_score": 0.2
  },
  "meta": {
    "warnings": []
  }
}
```

## 6.6 LLM phase (constrained Qwen)

Hard requirements for "constrained reasoning":

- `temperature=0` (or lowest available).
- System prompt explicitly forbids external knowledge.
- Output must include citations referencing cluster `chapter_id`.
- Fail-safe: if evidence missing, model must state insufficiency.
- Request payload to model includes only cluster JSON, not DB handles/tool instructions.

Implementation pattern:

- `/ask` builds cluster first.
- If `llm_enabled=false`: return deterministic artifact only.
- If `llm_enabled=true`: call `qwen_answer_from_cluster(cluster, req)` with timeout and bounded retries.

## 6.7 Error-handling policy

Recommended API behavior:

- `404`: run_id not found
- `422`: no seeds found for query
- `409`: enrichment version mismatch between run and available enriched data (when strict)
- `200 + warnings`: run has no edges and seed-only fallback chosen
- `504/502`: LLM timeout/provider failure while still returning cluster

## 7. Evidence from Live Queries (Feasibility Signal)

A direct DB prototype query on current data is already viable:

- Term: `actuator`
- Run: `5`
- Version: `v1_test`
- Seeds found: 4 chapters
- Expanded edges (score >= 0.2): 4
- Final cluster chapters: 5

This demonstrates the planned term -> DB -> run-scoped edge expansion -> cluster path works with current schema and data.

## 8. Performance and Scale Notes

At current dataset size, all relevant queries are sub-millisecond to low-millisecond.

Future scaling risk points:

- `ILIKE` term search on `chapter_text` (needs pg_trgm index for larger corpora).
- Edge expansion filtering/sorting by `(run_id + source ids + score)` (needs composite indexes).
- LLM context explosion (must keep strict chapter/field budgets).

## 9. Test Plan Required for `/ask`

Minimum additions:

- `test_ask_term_cluster_happy_path`
- `test_ask_rejects_missing_run`
- `test_ask_handles_version_mismatch`
- `test_ask_respects_hop_and_budget_limits`
- `test_ask_chapter_mode_exact_and_fuzzy_resolution`
- `test_qwen_prompt_is_grounded_and_citation_required`
- `test_ask_returns_cluster_when_llm_fails`

Also add test-run bootstrap guidance so `PYTHONPATH=.` is consistently applied in local/CI execution.

## 10. Recommended Delivery Sequence

1. Ship cluster-only `/ask` endpoint first (deterministic, no LLM call).
2. Add robust run/version validation and warning semantics.
3. Add Qwen adapter with strict grounding prompt and timeout controls.
4. Add composite DB indexes and optional pg_trgm term-search acceleration.
5. Add frontend integration against `graph_fragment` after backend contract stabilizes.

## 11. Bottom Line

The current repository already contains the core structural prerequisites for `/ask`:

- run-scoped graph edges,
- enriched chapter payloads in DB,
- stable FastAPI + SQLModel skeleton.

Main impediments are integration and data-contract integrity, not missing fundamentals.  
The most important blocker to resolve early is version integrity between `Run.enrichment_version` and `EnrichedChapter.enrichment_version`; without that, deterministic run-scoped Graph-RAG behavior is fragile even if the endpoint is implemented.
