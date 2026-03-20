# ChapterGraph

ChapterGraph builds a retrieval-backed chapter graph from technical books and serves it through FastAPI plus a lightweight D3 canvas frontend.

## Current MVP status

- Graph pipeline: available (`/compute-edges`, `/runs`, `/graph`)
- `/ask` MVP: available (term ask + chapter ask + cluster build + constrained LLM stub)
- LLM provider: `stub` by default, configurable via `config/llm.env`
- Vector-first seed retrieval: schema/backfill scripts are present, runtime switch is not enabled yet

## Project layout

```text
feature_achievement/
  api/
    main.py
    routers/
      edges.py
      ask.py
    schemas/
      ask.py
  ask/
    cluster_builder.py
  llm/
    prompts.py
    qwen_client.py
  db/
    engine.py
    models.py
    ask_queries.py
  scripts/
    init_db.py
    normalize_enrichment_version.py
    migrate_ask_vector.py
    build_enriched_embeddings.py
    smoke_ask_cluster.py
    smoke_ask.py

frontend/
  index.html
  app.js
  graph-core/
  graph-core-dist/
```

## Quick start

1. Initialize DB schema (first time only):

```bash
python -m feature_achievement.scripts.init_db
```

2. Start backend:

```bash
uvicorn feature_achievement.api.main:app --reload
```

3. Build frontend graph-core and start static server:

```bash
cd frontend
npm i
npm run build:core
python -m http.server 5500
```

4. Open UI:

```text
http://127.0.0.1:5500/index.html?api=http://127.0.0.1:8000
```

PowerShell one-click helper:

```powershell
.\scripts\run_local.ps1
```

## App config

Copy the app config template if you want to override the default local DB or
allow deployed frontend origins:

```bash
cp config/app.env.example config/app.env
```

Supported variables:

```env
DATABASE_URL=postgresql+psycopg2://postgres:1234@localhost:5432/chaptergraph
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

Notes:

- `DATABASE_URL` falls back to the current local Postgres default when unset.
- `CORS_ORIGINS` is a comma-separated allowlist for browser requests.

## LLM config

Copy template and fill your provider values:

```bash
cp config/llm.env.example config/llm.env
```

`config/llm.env.example`:

```env
QWEN_PROVIDER=stub
QWEN_BASE_URL=
QWEN_API_KEY=
QWEN_MODEL=qwen2.5-7b-instruct
```

Notes:

- If `QWEN_PROVIDER=stub`, `/ask` always returns deterministic stub markdown.
- If provider config is unsupported, `/ask` still returns 200 with `meta.llm_error`.

## Enrichment v2 runbook

```bash
python -m feature_achievement.scripts.migrate_enriched_shape_v2
python -m feature_achievement.scripts.validate_enriched_v2
python -m feature_achievement.scripts.migrate_enriched_v2_schema
python -m feature_achievement.scripts.import_enriched_chapters --overwrite
python -m feature_achievement.scripts.normalize_enrichment_version
```

## API overview

- `POST /compute-edges`: compute and persist graph edges for a run
- `GET /runs`: list runs
- `GET /graph?run_id=...`: fetch graph for frontend rendering
- `POST /ask`: run term/chapter retrieval + hop expansion + optional LLM answer

## `/ask` request examples

Term mode:

```json
{
  "query": "Explain actuator in Spring Boot",
  "query_type": "term",
  "run_id": 5,
  "enrichment_version": "v2_indexed_sections_bullets",
  "max_hops": 2,
  "seed_top_k": 5,
  "neighbor_top_k": 40,
  "min_edge_score": 0.2,
  "llm_enabled": true,
  "return_cluster": true,
  "return_graph_fragment": true
}
```

Chapter mode:

```json
{
  "query": "Explain this chapter",
  "query_type": "chapter",
  "chapter_id": "springboot-in-action::ch6",
  "run_id": 5,
  "enrichment_version": "v2_indexed_sections_bullets",
  "max_hops": 2,
  "llm_enabled": true,
  "return_cluster": true,
  "return_graph_fragment": true
}
```

Common error semantics:

- `404`: run not found
- `409`: request version and run version mismatch
- `422`: no seed chapter found

## Smoke scripts

Before `/ask` smoke on a fresh DB, normalize version labels once:

```bash
python -m feature_achievement.scripts.normalize_enrichment_version
```

Validate enriched v2 shape:

```bash
python -m feature_achievement.scripts.validate_enriched_v2
python -m feature_achievement.scripts.smoke_enriched_v2
```

Cluster-only path (no LLM call):

```bash
python -m feature_achievement.scripts.smoke_ask_cluster
```

Full `/ask` MVP path (term + chapter + LLM stub):

```bash
python -m feature_achievement.scripts.smoke_ask
```

Outputs:

- `tmp/ask_smoke_cluster.json`
- `tmp/ask_smoke_response.json`

## Vector schema/backfill scripts (prepared)

`pgvector` must be installed in PostgreSQL first.

```bash
python -m feature_achievement.scripts.migrate_ask_vector
python -m feature_achievement.scripts.build_enriched_embeddings
```

## Tests

```powershell
$env:PYTHONPATH='.'; pytest -q
```
