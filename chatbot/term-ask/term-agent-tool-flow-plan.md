2026-03-17

# Term Agent Tool Flow Plan

## Goal

Turn the current term-mode `/ask` chain into a clean service-oriented flow that can later be used as an agent sub-pipeline.

The immediate goal is not to build an agent.
The immediate goal is to:

- extract the current term orchestration from the router
- preserve current module boundaries as future tool boundaries
- standardize interfaces between retrieval, gating, recommendation, reranking, and answering

## Current Problem

Right now, term-mode logic is spread across:

- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)
- [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)
- [term_recommender.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_recommender.py)
- [candidate_anchor.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/candidate_anchor.py)
- [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py)

This already works, but the orchestration is still router-heavy.

If the term path is going to become part of a future agent flow, the router should stop being the place where the full execution policy lives.

## Target Architecture

The next target is a service layer:

- `feature_achievement/ask/term_flow.py`

This layer should orchestrate the existing modules without changing their core responsibilities.

## Module Responsibilities To Preserve

## 1. Cluster builder

Keep in:

- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)

Responsibility:

- term anchor -> seed -> graph expansion -> chapters -> evidence

Do not move recommendation or answer-mode policy into this module.

## 2. Retrieval quality gate

Keep in:

- [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)

Responsibility:

- decide whether retrieval is:
  - normal
  - broad_blocked
  - broad_allowed

Do not make this module own recommendation ranking.

## 3. Narrower-term generator

Keep in:

- [term_recommender.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_recommender.py)

Responsibility:

- semantic / heuristic candidate generation

Do not make this module own retrieval probing.

## 4. Candidate reranker

Keep in:

- [candidate_anchor.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/candidate_anchor.py)

Responsibility:

- probe candidates against current retrieval behavior
- rerank candidates by focus quality

## 5. Answer generator

Keep in:

- [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py)
- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)

Responsibility:

- prompt construction
- provider call
- answer generation

## New Layer To Add

## `term_flow.py`

Add:

- `feature_achievement/ask/term_flow.py`

This module should become the orchestration layer for term-mode ask.

It should be the first place where the current chain is expressed as a pipeline rather than as router conditionals.

## Proposed Service Interface

```python
def run_term_flow(
    *,
    req: AskRequest,
    session: Session,
) -> dict[str, object]:
    ...
```

This function should return a structured internal result, not an HTTP response model directly.

Suggested return shape:

```json
{
  "cluster_payload": {...},
  "evidence": {...},
  "response_state": "needs_narrower_term",
  "retrieval_warnings": {...},
  "response_guidance": null,
  "answer_markdown": null,
  "llm_error": null
}
```

This shape is service-oriented, not API-oriented.

## Recommended Internal Pipeline

Inside `run_term_flow(...)`, use this sequence:

## Step 1. Build cluster

Use:

- `build_cluster(session=session, req=req)`

Output:

- `cluster`
- `evidence`

## Step 2. Evaluate retrieval quality

Use:

- `evaluate_term_retrieval_quality(...)`

Output:

- `None`
- or retrieval warning object

## Step 3. If blocked, generate and rerank narrower terms

Use:

- `recommend_narrower_terms(...)`
- `rank_candidate_anchors(...)`

Output:

- reranked `suggested_terms`
- optional `suggested_term_diagnostics`

No LLM call here.

## Step 4. Select answer mode

Term flow should normalize into one of:

- `normal`
- `broad_overview`
- `needs_narrower_term`

This state should become explicit service output.

## Step 5. If answering is allowed, call LLM

For:

- `normal`
- `broad_overview`

Use:

- `ask_qwen(...)`

For `broad_overview`, pass downgraded `response_guidance`.

For `needs_narrower_term`, skip LLM.

## Step 6. Return structured service result

Do not assemble graph fragment here.
That remains router/output shaping logic.

The service should focus on the term flow itself.

## Router Refactor Direction

After `term_flow.py` exists, [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py) should become thinner.

Suggested router logic:

1. if `req.query_type == "term"`
   - call `run_term_flow(...)`
2. else
   - keep current chapter flow for now or later extract `chapter_flow.py`
3. transform service result into `AskResponse`
4. optionally build `graph_fragment`

This keeps HTTP handling separate from term decision logic.

## Standard Result Contracts

To make this future-agent-friendly, the intermediate contracts should be explicit.

## Retrieval result contract

Example:

```json
{
  "cluster_payload": {...},
  "evidence": {...}
}
```

## Quality result contract

Example:

```json
{
  "state": "broad_blocked",
  "message": "...",
  "term_too_broad": true
}
```

## Recommendation result contract

Example:

```json
{
  "suggested_terms": [...],
  "recommendation_reason": "spring_persistence",
  "recommendation_source": "rule_based",
  "recommendation_confidence": "heuristic"
}
```

## Candidate rerank result contract

Example:

```json
{
  "suggested_term_diagnostics": [
    {
      "term": "data persistence",
      "expected_response_state": "normal",
      "focus_state": "focused"
    }
  ]
}
```

## Service result contract

Example:

```json
{
  "response_state": "needs_narrower_term",
  "retrieval_warnings": {...},
  "answer_markdown": null,
  "response_guidance": null,
  "llm_error": null
}
```

This contract is important because later the same shape can be consumed by:

- router
- UI state logic
- future planner/agent tools

## What To Implement Next

## Phase A. Extract the service layer without changing behavior

Add `term_flow.py`.
Move term orchestration from router into it.

Do not change:

- response states
- prompt behavior
- recommendation logic
- reranking logic

This phase is purely structural.

## Phase B. Standardize internal helper functions

If needed, add tiny wrapper functions in `term_flow.py` such as:

```python
def _build_term_cluster(...)
def _evaluate_term_quality(...)
def _build_narrowing_payload(...)
def _generate_term_answer(...)
```

These wrappers help later tool extraction.

## Phase C. Only then consider chapter parity

After the term flow is clean, you can decide whether to:

- leave chapter flow in router
- or also extract `chapter_flow.py`

Do not force symmetry too early.

## Suggested Implementation Order

1. add `term_flow.py`
2. move current term branches from router into `run_term_flow(...)`
3. keep `AskResponse` assembly in router
4. keep graph fragment shaping in router
5. add tests that router behavior is unchanged

## Tests To Add

## Unit-level

For `term_flow.py`:

1. normal term request -> answer path
2. broad blocked request -> no LLM call, narrowing payload returned
3. broad overview request -> downgraded answer path
4. candidate rerank failure -> fallback to recommender order

## Integration-level

Existing API tests should continue to pass unchanged.

That is the main acceptance criterion for the refactor.

## Why This Matters For Agent Flow

Once `term_flow.py` exists, the current term pipeline becomes a clean callable unit.

That means later an agent can:

- call the whole flow as one guarded tool

or:

- call its sub-tools individually

depending on how much control you want.

Without this refactor, the logic stays trapped inside the HTTP layer.

## Non-Goals

Do not mix this plan with:

- Redis
- tool registry frameworks
- multi-agent orchestration
- memory persistence
- chapter-flow redesign

## Bottom Line

The next practical step after `term-agent-tool-flow.md` is:

- extract `term_flow.py`
- move orchestration out of the router
- preserve today’s modules as tomorrow’s tools

That gets the term path ready to become part of an agent pipeline without forcing an agent redesign now.
