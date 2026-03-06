# Plan: Make Retrieval Assembly Reusable and Make `similarity` a Real API Contract

## Goal

This document outlines how to refactor the current `POST /compute-edges` flow so that:

1. retrieval resources are no longer rebuilt inline inside the route handler,
2. `similarity` becomes a real request-level contract,
3. scorer selection is contract-driven and API-configurable in Level A,
4. the implementation stays incremental and low-risk.

Implementation status: Completed for Level A scope.

## Current Problem

Today, `feature_achievement/api/routers/edges.py` does all of this inside the route:

- load enriched books,
- filter books by `req.book_ids`,
- build chapter text map,
- build TF-IDF index,
- build token index,
- build candidate generator,
- branch on `req.similarity`,
- build scorer,
- build `RetrievalPipeline`.

That works, but it has three drawbacks:

1. the route knows too much about retrieval assembly,
2. `api/deps.py` is not really helping because its cached object is too fixed,
3. `ComputeEdgesRequest.similarity` is not a true interface contract.

## Key Design Point

The current cached helper in `api/deps.py` is not wrong, but it is too coarse.

It caches a single fully-built `RetrievalPipeline`, which hardcodes:

- all configured books,
- TF-IDF candidate generation,
- TF-IDF scoring,
- fixed `min_score`.

That shape does not fit `POST /compute-edges`, because this endpoint is request-driven:

- `book_ids` vary per request,
- `similarity` varies per request,
- `embedding_model` may vary per request,
- `min_score` varies per request.

So the better replacement is not "inject one cached pipeline". The better replacement is:

- cache reusable retrieval resources,
- assemble the final pipeline from those resources per request.

## Recommended Direction

Use a two-layer design:

1. `api/deps.py` (or a new service module) should build and cache reusable retrieval resources.
2. a small request-scoped runtime builder should assemble candidate generator, scorer, and pipeline from those resources.

This keeps FastAPI dependency injection useful without forcing all requests into one fixed pipeline.

## Q1 Answer: What can replace inline route rebuilding?

There are three viable replacements.

### Option A: Keep using FastAPI dependencies, but cache resource bundles instead of a final pipeline

This is the recommended option.

Why:

- fits FastAPI well,
- keeps expensive shared work out of the route,
- still allows request-level configurability,
- low disruption to current structure.

What gets cached:

- enriched books from config,
- chapter text map,
- maybe a TF-IDF index over the full configured corpus,
- maybe precomputed token resources.

What stays request-scoped:

- filtering to `req.book_ids`,
- scorer selection,
- embedding model choice,
- `min_score`,
- final `RetrievalPipeline`.

### Option B: Replace dependency helpers with a plain service/factory module

This is also good if you want less FastAPI-specific coupling.

Example:

- `feature_achievement/services/retrieval_factory.py`
- route calls `build_pipeline(req)` or `build_runtime(req)`

Why you might choose it:

- easier to unit test,
- avoids making complex business logic look like "dependency injection wiring",
- clearer separation between API layer and retrieval layer.

Tradeoff:

- slightly less idiomatic FastAPI than dependency-based composition.

### Option C: Build shared resources at app startup and store them on `app.state`

This is valid if the resource set is large and stable.

Example:

- during startup, compute shared retrieval assets,
- store on `app.state.retrieval_resources`,
- route reads from `request.app.state`.

Tradeoff:

- tighter lifecycle coupling to FastAPI app startup,
- harder to selectively invalidate,
- more awkward if you later support dynamic configs or hot reload of books.

## Recommendation

Choose Option A first.

It is the smallest clean improvement from the current code:

- keep `api/deps.py`,
- stop caching a fully-built `RetrievalPipeline`,
- start caching reusable retrieval inputs/resources instead.

If later the logic grows more complex, consider moving runtime assembly into a dedicated service module.

## Target Architecture

The route should become thin:

1. validate request,
2. get reusable retrieval resources from dependency,
3. build request-specific runtime from those resources,
4. generate edges,
5. persist run + graph data,
6. return result.

The retrieval assembly should move into a helper function (factory optional, not required in Level A).

## Proposed Refactor Structure

### 1. Make request model explicit and contract-driven

Change the request model from free-form strings to constrained values.

Recommended shape (two levels):

### Level A (minimal change, pragmatic)

Keep one request model, but make strategy-specific params explicit with conditional validation.

```python
from enum import Enum
from pydantic import BaseModel, model_validator


class SimilarityType(str, Enum):
    embedding = "embedding"
    tfidf = "tfidf"


class CandidateGeneratorType(str, Enum):
    tfidf_token = "tfidf_token"


class ComputeEdgesRequest(BaseModel):
    book_ids: list[str]
    enrichment_version: str = "v1_bullets+sections"
    candidate_generator: CandidateGeneratorType = CandidateGeneratorType.tfidf_token
    similarity: SimilarityType = SimilarityType.embedding
    embedding_model: str | None = None
    min_score: float = 0.1

    @model_validator(mode="after")
    def validate_strategy_options(self):
        if self.similarity == SimilarityType.embedding:
            # choose one policy:
            # 1) strict: require caller to pass embedding_model
            # 2) ergonomic: auto-fill default model
            self.embedding_model = self.embedding_model or "all-MiniLM-L6-v2"
        elif self.similarity == SimilarityType.tfidf:
            if self.embedding_model is not None:
                raise ValueError(
                    "embedding_model is only allowed when similarity='embedding'"
                )
        return self
```

This keeps API evolution cost low and immediately fixes the "misleading default string" issue.

### Level B (strict API contract, best docs)

Use a discriminated union so OpenAPI shows two different request schemas:

- `similarity="embedding"` requires `embedding_model`
- `similarity="tfidf"` does not allow `embedding_model`

```python
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


class ComputeEdgesBase(BaseModel):
    book_ids: list[str]
    enrichment_version: str = "v1_bullets+sections"
    candidate_generator: CandidateGeneratorType = CandidateGeneratorType.tfidf_token
    min_score: float = 0.1


class ComputeEdgesEmbedding(ComputeEdgesBase):
    similarity: Literal["embedding"] = "embedding"
    embedding_model: str = "all-MiniLM-L6-v2"


class ComputeEdgesTfidf(ComputeEdgesBase):
    similarity: Literal["tfidf"] = "tfidf"


ComputeEdgesRequest = Annotated[
    Union[ComputeEdgesEmbedding, ComputeEdgesTfidf],
    Field(discriminator="similarity"),
]
```

This is the cleanest contract design if you want callers and docs to be strictly aligned.

Why `Enum` instead of `str`:

- OpenAPI documents it clearly,
- invalid values fail early,
- route logic becomes explicit,
- later plugins are easier to register against enum/string keys.

`Literal[...]` and `Enum` are both valid. In this plan:

- use Level A first if you want minimal refactor risk,
- move to Level B when you want strict OpenAPI-level shape guarantees.

### 2. Replace cached `get_retrieval_pipline()` with cached shared resources

Instead of caching a final pipeline, cache a shared resource object.

Possible new object:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievalResources:
    enriched_books: list[dict]
    chapter_texts: dict[str, str]
```

Keep the cached dependency simple first:

```python
from functools import lru_cache
from feature_achievement.enrichment import load_all_enriched_data
from feature_achievement.retrieval.utils.text import collect_chapter_texts


@lru_cache
def get_retrieval_resources() -> RetrievalResources:
    enriched_books = load_all_enriched_data("book_content/books.yaml")
    chapter_texts = collect_chapter_texts(enriched_books)
    return RetrievalResources(
        enriched_books=enriched_books,
        chapter_texts=chapter_texts,
    )
```

This is safer than caching TF-IDF assets too early, because `POST /compute-edges` currently filters books by `req.book_ids`. If the retrieval index should reflect only the selected books, then indexing must still happen after filtering.

### 3. Add a request-scoped runtime builder

Introduce a function that takes:

- filtered books,
- request options,

and returns:

- candidate generator,
- similarity scorer,
- retrieval pipeline.

Example:

```python
from dataclasses import dataclass


@dataclass
class RetrievalRuntime:
    enriched_books: list[dict]
    chapter_texts: dict[str, str]
    tfidf_index: dict
    candidate_generator: object
    similarity_scorer: object
    pipeline: RetrievalPipeline
```

Runtime builder sketch (Level A, no scorer factory):

```python
def build_retrieval_runtime(
    enriched_books: list[dict],
    req: ComputeEdgesRequest,
) -> RetrievalRuntime:
    chapter_texts = collect_chapter_texts(enriched_books)
    tfidf_index = build_tfidf_index(chapter_texts)

    chapter_top_tokens = extract_top_tfidf_tokens(tfidf_index, top_n=20)
    token_index = build_token_index(chapter_top_tokens)
    candidate_generator = TfidfTokenCandidateGenerator(
        chapter_top_tokens=chapter_top_tokens,
        token_index=token_index,
        min_shared_tokens=2,
    )

    similarity_scorer = select_similarity_scorer(
        req=req,
        chapter_texts=chapter_texts,
        tfidf_index=tfidf_index,
    )

    pipeline = RetrievalPipeline(
        candidate_generator=candidate_generator,
        similarity_scorer=similarity_scorer,
        min_score=req.min_score,
    )

    return RetrievalRuntime(
        enriched_books=enriched_books,
        chapter_texts=chapter_texts,
        tfidf_index=tfidf_index,
        candidate_generator=candidate_generator,
        similarity_scorer=similarity_scorer,
        pipeline=pipeline,
    )
```

This is the main replacement for the current inline route code.

### 4. Keep the route responsible only for orchestration

After the refactor, the route should read roughly like this:

```python
@router.post("/compute-edges")
def compute_edges(
    req: ComputeEdgesRequest,
    session: Session = Depends(get_session),
    resources: RetrievalResources = Depends(get_retrieval_resources),
):
    run = Run(
        book_ids=json.dumps(req.book_ids),
        enrichment_version=req.enrichment_version,
        candidate_generator=req.candidate_generator.value,
        similarity=req.similarity.value,
        min_store=req.min_score,
    )
    session.add(run)
    session.commit()
    session.refresh(run)

    enriched_books = [
        b for b in resources.enriched_books if b["book_id"] in req.book_ids
    ]

    runtime = build_retrieval_runtime(enriched_books, req)
    edges = generate_edges(enriched_books, runtime.pipeline)

    persist_books_and_chapters(enriched_books, session)
    persist_edges(edges, run.id, session)

    return {
        "run_id": run.id,
        "count": len(edges),
        "message": "edges computed and stored successfully",
    }
```

This still performs request-specific runtime assembly, but the assembly is no longer embedded in the route.

## Why not use the current cached dependency directly?

Because `get_retrieval_pipline()` is caching the wrong abstraction level.

Its current output is too fixed:

- fixed corpus,
- fixed scorer,
- fixed score threshold.

For request-driven selection, you want one of these instead:

1. cached raw data,
2. cached reusable resource bundle.

You do not want one cached final pipeline unless every request shares the same settings.

## Detailed Implementation Steps

### Phase 1: Fix the API contract first

Status: Completed

Files:

- `feature_achievement/api/routers/compute_edges_request.py`

Tasks:

1. define `SimilarityType` as `Enum` or `Literal`,
2. define `CandidateGeneratorType` as `Enum` or `Literal`,
3. set `similarity` default to `embedding`,
4. set `candidate_generator` default to `tfidf_token`,
5. keep the rest unchanged.

Expected result:

- OpenAPI shows constrained values,
- callers know what values are legal,
- invalid values fail during validation instead of falling through silently.

### Phase 2: Replace dependency output shape

Status: Completed

Files:

- `feature_achievement/api/deps.py`

Tasks:

1. deprecate or remove `get_retrieval_pipline()`,
2. add `RetrievalResources`,
3. add `get_retrieval_resources()` with `@lru_cache`,
4. keep `get_db()` unchanged.

Expected result:

- dependency layer becomes reusable,
- route stops directly loading all enriched data itself.

### Phase 3: Introduce a request-scoped runtime builder helper

Status: Completed

Suggested location:

- keep it in `feature_achievement/api/routers/edges.py` first (smallest change), or
- extract to a small helper module later.

Tasks:

1. add `build_retrieval_runtime(...)`,
2. keep candidate generation explicit (TF-IDF token flow),
3. keep scorer selection driven by validated `similarity` contract,
4. centralize retrieval assembly outside the route body.

Expected result:

- route logic becomes smaller and easier to read,
- no factory abstraction is required for Level A.

### Phase 4: Thin down the route

Status: Completed

Files:

- `feature_achievement/api/routers/edges.py`

Tasks:

1. import `Depends(get_retrieval_resources)`,
2. filter cached `resources.enriched_books` by `req.book_ids`,
3. call `build_retrieval_runtime(enriched_books, req)`,
4. call `generate_edges(...)`,
5. persist as before,
6. remove route-local construction code.

Expected result:

- route becomes orchestration-only,
- behavior stays the same except for better validation and explicit scorer selection.

### Phase 5: Tighten error handling

Status: Completed

Files:

- `feature_achievement/api/routers/edges.py`

Tasks:

1. if `req.book_ids` filters to zero books, return `400`,
2. if unsupported `similarity` is encountered, raise clear error,
3. optionally validate `embedding_model` only when `similarity=embedding`.

Example:

```python
if not enriched_books:
    raise HTTPException(status_code=400, detail="No matching books for requested book_ids")
```

### Phase 6: Optional cleanup after the main refactor

Status: Completed (closed as optional/non-blocking for Level A)

Not required for the first pass, but worth tracking:

1. rename `get_retrieval_pipline()` to fix the typo if it remains anywhere,
2. rename DB field `Run.min_store` to `min_score` in a later schema migration,
3. consider moving request-to-runtime assembly out of the router package entirely,
4. add factory/registry only if scorer count grows.

## Suggested New File Layout

Minimal-change version:

```text
feature_achievement/
  api/
    deps.py
    routers/
      compute_edges_request.py
      edges.py
  retrieval/
    pipeline.py
    candidates/
    similarity/
    utils/
```

## Alternative: Cache more than just raw resources

If later performance matters, you can cache more aggressively.

Possible variants:

### Variant 1: Cache only enriched books

Best when:

- selected books vary a lot,
- you want correctness with minimal complexity.

### Variant 2: Cache enriched books + full chapter text map

Best when:

- parsing/enrichment is the main cost,
- per-request indexing cost is acceptable.

### Variant 3: Cache per-book or per-book-subset TF-IDF assets

Best when:

- traffic is high,
- the same book combinations are requested often.

Tradeoff:

- cache invalidation and key design get more complex quickly.

For this codebase, Variant 1 or 2 is the right first step.

## Compatibility Notes

### Backward compatibility for API callers

Changing:

```python
similarity: str = "tfidf/embedding"
```

to:

```python
similarity: SimilarityType = SimilarityType.embedding
```

means callers sending `"tfidf/embedding"` will now fail validation.

That is good in principle, but it is a contract change. If you need compatibility, you can temporarily accept the old value and map it to a real default before removing it.

Example compatibility shim:

```python
from pydantic import field_validator


@field_validator("similarity", mode="before")
@classmethod
def normalize_similarity(cls, value):
    if value == "tfidf/embedding":
        return "embedding"
    return value
```

This should only be temporary if used at all. //don't worry about that,`"tfidf/embedding"`this is deprecated

## Testing Plan

Do not implement these changes without adding at least minimal verification.

Status: Completed

### API contract tests

Verify:

1. OpenAPI shows `similarity` enum values.
2. default request uses `embedding`.
3. invalid `similarity` is rejected with `422`.
4. invalid `candidate_generator` is rejected with `422`.

### Route behavior tests

Verify:

1. route still persists a `Run`,
2. route persists edges,
3. `req.similarity=tfidf` uses TF-IDF scorer,
4. `req.similarity=embedding` uses embedding scorer,
5. empty `book_ids` selection returns a clear error.

## Recommended Implementation Order

1. update `ComputeEdgesRequest` to use real enums/literals + conditional validation,
2. add shared `RetrievalResources` dependency,
3. refactor route to consume scorer selected from the validated `similarity` contract,
4. add a small request-scoped runtime builder helper (no factory),
5. add validation/error handling and API tests,
6. optionally clean up naming and older helper functions.

## Expected End State

After this refactor:

- `similarity` is a real API contract, not a misleading free-form string,
- `candidate_generator` becomes structurally extensible,
- the route stops manually assembling retrieval internals,
- `api/deps.py` becomes useful at the right abstraction level.

## Bottom Line

The right replacement for the current inline route assembly is not "inject one cached final pipeline". It is "inject cached reusable retrieval resources, then build a request-specific runtime with contract-driven strategy dispatch."

That gives you both:

- clear Level A strategy behavior,
- API configurability,

without locking the endpoint into one global retrieval configuration.
