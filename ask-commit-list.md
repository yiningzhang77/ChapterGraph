# ask-commit-list.md

Date: 2026-03-07  
Goal: Implement the `/ask` MVP based on `ask-plan.md` (term + chapter + LLM dialogue)

## Progress Snapshot (2026-03-08)

- Completed commits: `01`, `02`, `03`, `04`, `05`, `06`, `08`, `09`, `10`
- In progress: none
- Remaining commits: `07`

---

## [x] Commit 01 - `chore(db): normalize enrichment_version to v1_bullets+sections`

Purpose:
- Unify the version naming in `run` and `enriched_chapter` and remove Blocker A.

Changes:
- add `feature_achievement/scripts/normalize_enrichment_version.py`

Run:
- `python -m feature_achievement.scripts.normalize_enrichment_version`

Verify:
- Use SQL to confirm that both tables only contain `v1_bullets+sections`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 02 - `feat(api): add /ask request-response schema and runtime version guard`

Purpose:
- Create the initial `/ask` API shell, including the default enrichment version and the `409` mismatch rule.

Changes:
- add `feature_achievement/api/schemas/ask.py`
- add `feature_achievement/api/schemas/__init__.py`
- add `feature_achievement/api/routers/ask.py`
- update `feature_achievement/api/main.py` (mount ask router)

Verify:
- `GET /openapi.json` includes `/ask`
- a mismatch request returns `409`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 03 - `feat(cluster): implement deterministic cluster builder (ilike path, hop2)`

Purpose:
- Implement the MVP core flow: term/chapter -> seed -> hop2 -> cluster.

Changes:
- add `feature_achievement/ask/__init__.py`
- add `feature_achievement/ask/cluster_builder.py`
- add `feature_achievement/db/ask_queries.py`
- update `feature_achievement/api/routers/ask.py` (use builder)

Verify:
- a term request returns `cluster.chapters` and `cluster.edges`
- a chapter request returns results via `chapter_id`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 04 - `feat(llm): add constrained prompt and qwen adapter (stub first)`

Purpose:
- Wire up the LLM invocation path: make the stub version work first, then switch to the real provider.

Changes:
- add `feature_achievement/llm/__init__.py`
- add `feature_achievement/llm/prompts.py`
- add `feature_achievement/llm/qwen_client.py`
- update `feature_achievement/api/routers/ask.py` (llm_enabled flow)

Verify:
- `llm_enabled=true` returns `answer_markdown` (stub)
- provider failures return `meta.llm_error`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 05 - `feat(config): add LLM config template for API key`

Purpose:
- Add a local configuration template for secrets without committing a real API key.

Changes:
- add `config/llm.env.example`
- update `.gitignore` (ignore `config/llm.env`)
- optional: update `feature_achievement/llm/qwen_client.py` (load local env file if it exists)

Suggested `config/llm.env.example`:
- `QWEN_PROVIDER=stub`
- `QWEN_BASE_URL=`
- `QWEN_API_KEY=`
- `QWEN_MODEL=qwen2.5-7b-instruct`

Verify:
- after copying the template to `config/llm.env`, the service can read the config
- if no API key is configured, stub mode still works without error

---

## [x] Commit 06 - `feat(vector): add pgvector schema and embedding backfill scripts`

Purpose:
- Introduce the “vector-first” seed search capability.

Changes:
- add `feature_achievement/scripts/migrate_ask_vector.py`
- add `feature_achievement/scripts/build_enriched_embeddings.py`

Run:
- `python -m feature_achievement.scripts.migrate_ask_vector`
- `python -m feature_achievement.scripts.build_enriched_embeddings`

Verify:
- `enriched_chapter_embedding` contains data
- `$env:PYTHONPATH='.'; pytest -q`

Status note:
- scripts are implemented and runnable
- current local PostgreSQL is missing `pgvector` extension, so migration exits with a clear instruction

---

## [ ] Commit 07 - `feat(retrieval): enable vector-first seed search with ilike fallback`

Purpose:
- Implement `seed_search=auto|vector|ilike`, with `auto` as the default.

Changes:
- update `feature_achievement/db/ask_queries.py` (vector search query)
- add `feature_achievement/ask/vector_embedder.py`
- update `feature_achievement/ask/cluster_builder.py` (auto fallback logic)
- update `feature_achievement/api/schemas/ask.py` (seed_search enum)

Verify:
- `seed_search=vector` produces a clear error or follows the designed fallback when vector data is unavailable
- `seed_search=auto` automatically falls back to `ilike` when vector search is unavailable
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 08 - `feat(frontend): add /ask chat panel (term + chapter ask)`

Purpose:
- Integrate the frontend chat panel and support both term-based and chapter-based questions.

Changes:
- update `frontend/app.js` (chat state + askByTerm + askByChapter)
- update `frontend/index.html` (chat panel styles/layout)
- optional: update `frontend/graph-core/types.ts` if needed for selected chapter state

Verify:
- `npm run build:core` passes
- the page can submit a term query and display an answer
- the user can ask a question about a selected chapter

---

## [x] Commit 09 - `test(ask): add ask API/cluster/llm tests`

Purpose:
- Prevent regressions and keep the MVP safe to iterate on.

Changes:
- add `tests/test_ask_request.py`
- add `tests/test_ask_cluster_builder.py`
- add `tests/test_ask_api.py`
- add `tests/test_qwen_prompts.py`

Verify:
- `$env:PYTHONPATH='.'; pytest -q`
- cover 404/409/422, term/chapter flows, and the llm stub branch

---

## [x] Commit 10 - `docs(ask): update README and mark ask-plan phases completed`

Purpose:
- Complete the documentation and delivery loop.

Changes:
- update `README.md` (`/ask` usage + config + smoke examples)
- update `ask-plan.md` (mark each phase as completed)
- add `feature_achievement/scripts/smoke_ask.py`

Verify:
- the README examples run successfully
- `python -m feature_achievement.scripts.smoke_ask`

---

## Continuous Checks (each commit)

- Backend tests: `$env:PYTHONPATH='.'; pytest -q`
- Frontend build: `npm run build:core`
- API manual smoke:
  - `POST /ask` term
  - `POST /ask` chapter
