# plan.md — Implement `/ask` (Run-scoped Graph-RAG: Term → DB → Cluster → LLM)

## 0. Context + Goals

### Repository reality (baseline)

* API entry is `feature_achievement/api/main.py`, currently mounting a single router from `feature_achievement/api/routers/edges.py`. 
* DB has both `Chapter` (minimal) and `EnrichedChapter` (richer JSON signals), but the visible graph API still uses the minimal `Chapter` path today. 
* Retrieval is already run-scoped: `Run` + `Edge(run_id=...)`; edges are directional and typically stored in both directions. 

### Feature definition

Implement `/ask` as a **run-scoped Graph-RAG query service**:

* **Input**: query + `run_id` + `enrichment_version` + mode (term|chapter)
* **Server**: deterministically builds a **Cognitive Cluster** from DB (and only DB/file-backed assets already imported), using:

  * term → seed chapters from `enriched_chapter`
  * expand via `edges` (1–2 hop) under `run_id`
  * fetch enriched payload for all cluster chapters
  * optional evidence snippets / matched signals
* **LLM**: Qwen is used strictly as a *constrained reasoning engine* over the cluster JSON (no tool use, no DB access, no “free knowledge”).
* **Output**: cluster + explanation (and optional UI-friendly graph fragment).

This aligns with your Phase-4 “Term → Database → Cluster → LLM” spec. 

---

## 1. Non-goals (keep scope tight)

* No agent/tool-calling that lets the model fetch DB rows.
* No recomputation of TF-IDF/embedding indexes in `/ask` (run pipeline owns that).
* No new “graph construction” logic in `/ask`; it only consumes `edges` + `enriched_chapter`.
* No full-doc parsing: enrichment is still TOC-signal-based (`chapter_text` from bullets/sections). 

---

## 2. Proposed API Contract

### Endpoint

`POST /ask`

### Request (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class AskRequest(BaseModel):
    query: str = Field(..., min_length=1)
    query_type: Literal["term", "chapter"] = "term"
    run_id: int

    enrichment_version: str = "v1"   # must match values used at import time
    # expansion controls
    max_hops: int = Field(1, ge=0, le=2)
    seed_top_k: int = Field(5, ge=1, le=50)
    neighbor_top_k: int = Field(20, ge=1, le=200)
    min_edge_score: float = Field(0.2, ge=0.0, le=1.0)

    # output controls
    return_cluster: bool = True
    return_graph_fragment: bool = True
    llm_enabled: bool = True
    llm_model: Optional[str] = "qwen"  # later: qwen2.5 etc.
```

### Response

```python
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class AskResponse(BaseModel):
    query: str
    query_type: str
    run_id: int
    enrichment_version: str

    # deterministic artifact
    cluster: Optional[Dict[str, Any]] = None

    # LLM result (grounded)
    answer_markdown: Optional[str] = None

    # UI support
    graph_fragment: Optional[Dict[str, Any]] = None

    meta: Dict[str, Any] = {}
```

---

## 3. Data Model + Indexing Requirements

### Tables used by `/ask`

* `EnrichedChapter` (source: `*_enriched.json` imported via your CLI)
* `Edge` (run-scoped, directional, `run_id`)
* optionally `Run` (validate run existence, record config)

### Must-have DB indices (Postgres)

Add in migration / init step (or in SQLModel with `index=True`):

* `edge(run_id, from_chapter)`
* `edge(run_id, to_chapter)` (optional, helps reverse lookups)
* `enriched_chapter(chapter_id)` (PK)
* `enriched_chapter(book_id, enrichment_version)`
* if you do term search via `ILIKE` on `chapter_text`, consider `GIN` trigram later (optional, can wait).

---

## 4. Implementation Architecture

Create 4 layers:

1. **Router**: `feature_achievement/api/routers/ask.py`
2. **Cluster Builder**: `feature_achievement/ask/cluster_builder.py`
3. **DB Query Helpers**: extend `feature_achievement/db/crud.py` (or add `db/queries.py`)
4. **LLM Adapter + Prompts**: `feature_achievement/llm/qwen_client.py` + `feature_achievement/llm/prompts.py`

Also update `api/main.py` to mount the new router (right now it only mounts `edges.py`). 

---

## 5. Deterministic Cognitive Cluster Spec

### Cluster JSON structure (what the model sees)

```json
{
  "schema_version": "cluster.v1",
  "query": "...",
  "query_type": "term|chapter",
  "run_id": 12,
  "enrichment_version": "v1",

  "seed": {
    "seed_chapter_ids": ["book::ch3", "book::ch7"],
    "seed_reason": "term_match|chapter_lookup"
  },

  "chapters": [
    {
      "chapter_id": "spring-in-action::ch3",
      "book_id": "spring-in-action",
      "title": "...",
      "chapter_text": "...",
      "signals": {
        "sections": [...],
        "bullets": [...]
      }
    }
  ],

  "edges": [
    {
      "from": "spring-in-action::ch3",
      "to": "spring-start-here::ch14",
      "score": 0.2991,
      "type": "tfidf"
    }
  ],

  "constraints": {
    "max_hops": 1,
    "seed_top_k": 5,
    "neighbor_top_k": 20,
    "min_edge_score": 0.2,
    "notes": "LLM must not use external knowledge; answer must cite chapters listed above."
  }
}
```

This mirrors your Phase-4 intent: build a closed cluster from `enriched_chapter` + `edges` then let LLM explain. 

---

## 6. Cluster Builder Logic (core of /ask)

### 6.1 Query parsing

* `query_type="term"`: search enriched chapters to produce `seed_chapter_ids`
* `query_type="chapter"`: resolve the chapter (by id or by fuzzy title match inside a book), produce exactly one seed

### 6.2 Seed selection (Term search MVP)

Start simple (works now, improve later):

* `ILIKE %term%` over `EnrichedChapter.chapter_text`
* also search `title` if available in EnrichedChapter payload
* sort by a cheap heuristic: number of occurrences, then length-normalized

Later upgrades (optional):

* tokenization + BM25
* Postgres trigram index
* store precomputed keyphrases to match exact terms

### 6.3 Graph expansion (run-scoped)

Given `seed_chapter_ids`:

* hop 1: fetch outgoing edges `Edge(run_id, from in seeds)` with `score>=min_edge_score`, top-N by score
* hop 2 (if `max_hops=2`): repeat from hop1 targets (but enforce budget)

Important: your stored edges are directional; assume both directions may exist but don’t rely on it. 

### 6.4 Fetch enriched payloads

For all chapter_ids in `seed ∪ expanded`:

* fetch `EnrichedChapter` rows filtered by `enrichment_version`

### 6.5 Budgeting + field whitelist

Before handing to LLM:

* cap `chapters` count (e.g., <= 30)
* truncate `chapter_text` to N chars/tokens
* drop heavy signals if needed (keep titles + 1–2 signals)

This is exactly the “token budget + whitelist fields” approach you want for constrained reasoning. 

---

## 7. DB helper functions (CRUD/query layer)

Add functions (either in `db/crud.py` or a new `db/ask_queries.py`):

```python
from sqlmodel import Session, select
from feature_achievement.db.models import EnrichedChapter, Edge

def search_enriched_chapters_by_term(
    session: Session,
    term: str,
    enrichment_version: str,
    limit: int,
):
    pattern = f"%{term}%"
    stmt = (
        select(EnrichedChapter)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.chapter_text.ilike(pattern))
        .limit(limit)
    )
    return session.exec(stmt).all()

def get_edges_from_sources(
    session: Session,
    run_id: int,
    source_ids: list[str],
    min_score: float,
    limit: int,
):
    stmt = (
        select(Edge)
        .where(Edge.run_id == run_id)
        .where(Edge.from_chapter.in_(source_ids))
        .where(Edge.score >= min_score)
        .order_by(Edge.score.desc())
        .limit(limit)
    )
    return session.exec(stmt).all()

def get_enriched_chapters_by_ids(
    session: Session,
    chapter_ids: list[str],
    enrichment_version: str,
):
    stmt = (
        select(EnrichedChapter)
        .where(EnrichedChapter.enrichment_version == enrichment_version)
        .where(EnrichedChapter.chapter_id.in_(chapter_ids))
    )
    return session.exec(stmt).all()
```

---

## 8. Router + Wiring

### 8.1 Create `feature_achievement/api/routers/ask.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from feature_achievement.db.engine import get_session
from feature_achievement.ask.cluster_builder import build_cluster
from feature_achievement.llm.qwen_client import qwen_answer_from_cluster
from feature_achievement.api.schemas.ask import AskRequest, AskResponse

router = APIRouter()

@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, session: Session = Depends(get_session)):
    cluster = build_cluster(session=session, req=req)

    answer = None
    if req.llm_enabled:
        answer = qwen_answer_from_cluster(cluster=cluster, req=req)

    graph_fragment = None
    if req.return_graph_fragment:
        graph_fragment = {
            "nodes": [{"id": c["chapter_id"], "book_id": c["book_id"], "title": c["title"]} for c in cluster["chapters"]],
            "edges": cluster["edges"],
        }

    return AskResponse(
        query=req.query,
        query_type=req.query_type,
        run_id=req.run_id,
        enrichment_version=req.enrichment_version,
        cluster=cluster if req.return_cluster else None,
        answer_markdown=answer,
        graph_fragment=graph_fragment,
        meta={"schema_version": cluster.get("schema_version", "cluster.v1")},
    )
```

### 8.2 Mount router in `feature_achievement/api/main.py`

Currently only edges router is mounted. 
Update to:

```python
from fastapi import FastAPI
from feature_achievement.api.routers import edges, ask

app = FastAPI()
app.include_router(edges.router)
app.include_router(ask.router)
```

---

## 9. Qwen Adapter + Prompts (Constrained Reasoning)

### 9.1 Prompt strategy: “task-aware” + schema-bound

We will not do free-form chat. We do:

* System: strict grounding rules
* User: includes cluster JSON + explicit required output sections

```python
SYSTEM = """You are a grounded reasoning engine.
You must ONLY use facts present in the provided JSON cluster.
Do NOT use external knowledge.
When you make a claim, cite the chapter_id(s) you used.
If evidence is insufficient, say so explicitly."""
```

### 9.2 User prompt template (term mode)

```python
def build_term_prompt(cluster: dict, query: str) -> str:
    return f"""
Task: TERM_LOCATION_AND_RELATIONSHIP
Query: {query}

You are given a JSON cluster. Do:
1) List where the term appears (book_id, chapter_id, title).
2) Pick top 3 most relevant chapters and explain why (use edge scores + chapter_text).
3) Summarize how these chapters relate (graph-aware explanation).
4) Output in Markdown with a final "Citations" section listing chapter_ids used.

JSON Cluster:
{json.dumps(cluster, ensure_ascii=False)}
""".strip()
```

### 9.3 User prompt template (chapter mode)

```python
def build_chapter_prompt(cluster: dict, chapter_id: str) -> str:
    return f"""
Task: CHAPTER_RELATION_EXPLANATION
Seed chapter: {chapter_id}

Explain:
1) Immediate neighbors (1-hop) and why connected (use edge score/type).
2) Conceptual clusters among neighbors (max 3 clusters).
3) Suggested learning order (must be justified by edges/signals).
4) Include citations (chapter_id).

JSON Cluster:
{json.dumps(cluster, ensure_ascii=False)}
""".strip()
```

This matches the “Cognitive Cluster as unified reasoning protocol + constrained reasoning” direction. 

---

## 10. Optional: Redis cache (later commit)

Only cache **final assembled cluster** and optionally **final answer**.

Key:
`cluster:{run_id}:{enrichment_version}:{query_type}:{normalized_query}:{max_hops}:{min_edge_score}`

Value:

* cluster JSON
* answer_markdown (optional)

TTL:

* 10–30 minutes dev default

This is an optimization; correctness must not depend on Redis.

---

## 11. Testing + Debuggability

### 11.1 Add a smoke script

`feature_achievement/scripts/smoke_ask.py`

* checks run exists
* asks a term known to exist
* prints cluster size, edge count
* prints answer length

### 11.2 Minimal unit tests (even 3 tests help)

* `test_cluster_builder_term_returns_seed_and_edges()`
* `test_cluster_builder_respects_budget()`
* `test_llm_prompt_includes_constraints_and_schema()`

Repo currently has no tests, so even a tiny suite improves reliability. 

---

## 12. Commit Plan (recommended split)

1. `feat(db): add ask query helpers for enriched chapters and run edges`
2. `feat(cluster): add CognitiveCluster schema and deterministic builder`
3. `feat(api): add /ask endpoint (cluster-only, no LLM)`
4. `feat(llm): add Qwen adapter + task-aware prompts for constrained reasoning`
5. `feat(cache): add Redis memoization for /ask (optional)`
6. `docs: add ask design + data lifecycle docs`

---

## 13. Known risks + cleanup items (do opportunistically)

* `enrichment.py` loads spaCy model at import time but current enrichment doesn’t use it; can break env setup. Consider lazy-loading or removing. 
* `/compute-edges` request model fields imply configurability that route doesn’t honor (candidate_generator default mismatch etc.); not required for `/ask`, but keep it in mind for later API polish. 

