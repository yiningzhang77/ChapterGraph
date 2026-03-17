# Chatbot Preview Launch Steps

Goal: make the current `chatbot / ask` flow "can run, can test, can observe" as an internal preview release.

Scope for this phase:
- `Ask by Term`
- `Ask by Chapter`
- single-turn answer
- deterministic cluster retrieval
- real LLM provider or explicit LLM failure

Out of scope for this phase:
- multi-turn memory
- agent loop / planner
- user-uploaded corpora
- autonomous retries / orchestration

## Step 1. Freeze the preview target

Do not keep changing data shape and deployment target at the same time.

Decide and write down:
- one fixed `run_id` for preview
- one fixed `enrichment_version`
- one backend URL
- one frontend URL

Current recommended data target:
- `enrichment_version = v2_indexed_sections_bullets`

Acceptance:
- you know exactly which run the preview is using
- all later smoke checks use the same run unless intentionally changed

## Step 2. Verify the current local baseline with stub LLM

Before wiring a real model, confirm the whole request path is already healthy.

Run:

```powershell
python -m pytest -q
python -m feature_achievement.scripts.smoke_ask_cluster
python -m feature_achievement.scripts.smoke_ask
powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1
```

Check:
- tests pass
- cluster smoke passes
- `/ask` smoke passes
- frontend can send both term and chapter asks
- stub answer is rendered in the UI

If this step is not stable, do not proceed to deployment.

## Step 3. Lock the preview run

Use `/runs` and choose a run that actually has usable edges and the correct enrichment version.

What to confirm:
- `run_id` exists
- the run is for the books you want to preview
- the run has enough `edge` coverage to make term ask useful

Practical rule:
- do not rely on "latest run"
- hardcode or configure the preview run in your manual checklist

## Step 4. Wire the real Qwen provider

This is the main missing backend piece.

Current state:
- [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py) only supports `QWEN_PROVIDER=stub`
- any other provider raises `Unsupported QWEN_PROVIDER`

Implement:
- real HTTP call in [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py)
- keep `stub` branch for local fallback
- load config from [llm.env.example](C:/Users/hy/ChapterGraph/config/llm.env.example) -> `config/llm.env`

Required config:
- `QWEN_PROVIDER`
- `QWEN_BASE_URL`
- `QWEN_API_KEY`
- `QWEN_MODEL`

Recommended config:
- `QWEN_TEMPERATURE=0`
- `QWEN_MAX_TOKENS`

Acceptance:
- valid config returns non-empty `answer_markdown`
- invalid config does not crash `/ask`
- invalid config is surfaced as `meta.llm_error`

## Step 5. Add a real-provider smoke path

Current [smoke_ask.py](C:/Users/hy/ChapterGraph/feature_achievement/scripts/smoke_ask.py) forces `QWEN_PROVIDER=stub`.

You need one of:
- add a `--provider real` style switch to the existing smoke script
- or add a second smoke script for real LLM validation

Minimum smoke coverage:
- one term-mode request
- one chapter-mode request

Smoke output should include:
- `run_id`
- query
- query type
- chapter count
- edge count
- evidence bullet count
- whether `answer_markdown` is empty
- whether `meta.llm_error` exists

Acceptance:
- both requests return `200`
- answer is non-empty when provider is healthy
- failures are explicit when provider is unhealthy

## Step 6. Add minimum observability for `/ask`

Current repo has smoke scripts, but almost no runtime observability.

Before preview deployment, add these three things.

### 6.1 Structured ask logs

For every `/ask` request, log:
- request id
- timestamp
- query type
- run id
- chapter id
- enrichment version
- chapter count in cluster
- edge count in cluster
- evidence bullet count
- llm enabled
- llm model
- llm latency ms
- llm error

This can start as plain backend logs.

### 6.2 Health endpoints

Add:
- `/healthz` for process alive
- optionally `/readyz` for DB-ready

Acceptance:
- backend health can be checked without using the full UI

### 6.3 Persisted ask traces

Choose one:
- file-based `tmp/ask_logs.jsonl`
- DB table such as `ask_trace`

Recommended direction:
- use a DB table if you want to compare query quality over time

Minimum fields:
- request id
- query
- query type
- run id
- chapter id
- status
- llm error
- created at

## Step 7. Harden the frontend for preview use

The current frontend is already usable, but still developer-shaped.

Before preview release, make sure the UI clearly shows:
- current `run_id`
- current ask mode
- selected chapter in chapter mode
- loading state
- request failure state
- model failure state if `meta.llm_error` exists

Important:
- term ask should not show chapter-selection hint
- chapter ask should clearly show which chapter is selected

Acceptance:
- a non-developer can tell what the system is asking against
- a failure can be distinguished as backend failure vs model failure

## Step 8. Prepare the deployment shape

Use the smallest deployment split first.

Recommended:
- backend: FastAPI service
- frontend: static site
- config: server-side `config/llm.env`

Before deployment, update CORS in [main.py](C:/Users/hy/ChapterGraph/feature_achievement/api/main.py).

Current state:
- only localhost origins are allowed

For preview deployment:
- add the real frontend origin
- keep localhost if you still want local dev

## Step 9. Write a manual release checklist

Do not deploy by intuition. Use a fixed checklist.

Minimum checklist:
1. `/healthz` returns `200`
2. `/runs` returns data
3. `/graph?run_id=...` returns data
4. term ask succeeds
5. chapter ask succeeds
6. term ask no-hit path returns explicit error
7. chapter ask without selected chapter is blocked in UI
8. invalid LLM key produces visible `meta.llm_error`
9. ask trace/log is recorded

## Step 10. Run a short observation window after preview release

Do not immediately redesign enrichment after the first deployment.

Observe for 1 to 3 days:
- which term queries fail to find good seeds
- whether chapter ask is noticeably better than term ask
- whether evidence bullets are sufficient for grounded answers
- how often LLM errors happen
- whether failures are retrieval problems or generation problems

Only after this should you decide:
- whether current cluster/evidence is enough
- whether enrichment should be changed again
- whether memory/session work should start

## Recommended execution order

If you want the shortest path, do it in this order:

1. pass all current tests and smoke scripts
2. freeze one preview `run_id`
3. wire real Qwen provider
4. add real-provider smoke
5. add `/ask` logs + health endpoint
6. harden frontend states
7. deploy preview
8. observe failures before changing retrieval/enrichment

## Definition of done for this preview phase

This phase is done only if all are true:
- `/ask` works for both term and chapter mode
- real LLM can answer through the deployed backend
- failures are visible and diagnosable
- one fixed preview run is being used
- smoke tests can be rerun after deployment
- you can inspect logs/traces for real user asks
