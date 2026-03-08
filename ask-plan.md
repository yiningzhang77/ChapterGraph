# ask-plan.md

Date: 2026-03-08
Scope: `/ask` MVP delivery plan and execution status

## Goal

Implement a minimal deterministic Graph-RAG `/ask` path:

- term query -> seed chapters -> hop2 expansion -> cluster -> constrained LLM answer
- chapter query -> selected chapter seed -> hop2 expansion -> cluster -> constrained LLM answer

## Phase Status

- [x] Phase 0: unblock version naming (`v1_bullets+sections`)
- [x] Phase 1: define `/ask` request/response schema and router shell
- [x] Phase 2: implement deterministic cluster builder (term/chapter, hop2)
- [x] Phase 3: add constrained prompt + Qwen adapter (`stub` first)
- [x] Phase 4: frontend chat panel (ask by term / ask by chapter)
- [x] Phase 5: tests for schema, cluster builder, API, prompt/client
- [x] Phase 6: docs + smoke scripts (`smoke_ask_cluster.py`, `smoke_ask.py`)
- [ ] Phase 7: vector-first runtime seed search (`auto|vector|ilike`) - deferred to Commit 07

## Delivered Implementation (Completed)

### 1. Data and runtime guard

- Normalized enrichment version to `v1_bullets+sections`
- `/ask` enforces run/version consistency (`409` when mismatch)

### 2. `/ask` API contract

Implemented in:

- `feature_achievement/api/schemas/ask.py`
- `feature_achievement/api/routers/ask.py`
- `feature_achievement/api/main.py`

Core fields:

- input: `query`, `query_type`, `run_id`, `chapter_id`, retrieval knobs, LLM knobs
- output: `answer_markdown`, optional `cluster`, optional `graph_fragment`, `meta`

### 3. Deterministic cluster path

Implemented in:

- `feature_achievement/ask/cluster_builder.py`
- `feature_achievement/db/ask_queries.py`

Behavior:

- `term`: ILIKE seed search over `enriched_chapter`
- `chapter`: direct chapter resolution
- expansion: up to hop2 (`max_hops<=2`) by `edge` table and score threshold
- cluster payload: `seed`, `chapters`, `edges`, `constraints`

### 4. LLM path (MVP)

Implemented in:

- `feature_achievement/llm/prompts.py`
- `feature_achievement/llm/qwen_client.py`

Behavior:

- constrained prompt requiring chapter citations
- `stub` provider by default
- provider errors are captured in `meta.llm_error`

### 5. Frontend integration

Implemented in:

- `frontend/app.js`
- `frontend/index.html`

Behavior:

- ask panel with mode switch (term/chapter)
- chapter mode uses selected chapter node from canvas
- message list shows user query and assistant answer

### 6. Regression coverage

Implemented tests:

- `tests/test_ask_request.py`
- `tests/test_ask_cluster_builder.py`
- `tests/test_ask_api.py`
- `tests/test_qwen_prompts.py`

Coverage highlights:

- `404` missing run
- `409` version mismatch
- `422` no seed found
- successful term/chapter flows
- llm stub and provider error handling

## Smoke verification

Run:

```powershell
$env:PYTHONPATH='.'; pytest -q
python -m feature_achievement.scripts.smoke_ask_cluster
python -m feature_achievement.scripts.smoke_ask
```

Expected:

- tests pass
- smoke scripts produce non-empty cluster and answer fields
- output files are generated in `tmp/`

## Pending work (not part of Commit 10)

- Commit 07: enable runtime vector-first seed retrieval (`seed_search=auto|vector|ilike`)
- Optional: wire real Qwen provider endpoint and auth
