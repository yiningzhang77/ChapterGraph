2026-03-17

# Term Agent Tool Flow

## Purpose

This note organizes the current term-mode `/ask` chain as a future agent-flow component.

The goal is not to redesign the system into an agent now.
The goal is to make clear:

- what the current term pipeline already does
- which parts are already tool-like
- how the interfaces should be abstracted next
- how the pieces could be composed later as an agent pipeline

## Current Term Chain

Today the term path is effectively:

1. receive:
   - `term`
   - optional `user_query`
2. build cluster from the term anchor
3. evaluate retrieval quality
4. if blocked:
   - generate narrower-term candidates
   - rerank them with candidate-anchor probing
   - return narrowing guidance
5. if allowed:
   - optionally downgrade to broad-overview mode
   - call LLM
6. return:
   - answer or block
   - retrieval warnings
   - suggested terms
   - optional candidate diagnostics

So the current chain is already more than “retrieve then answer”.
It already has:

- anchor selection
- retrieval
- quality gating
- candidate generation
- candidate reranking
- answer-mode selection

That is already a proto-agent flow.

## Current Concrete Modules

## 1. Request schema

- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/schemas/ask.py)

Current term contract:

- `term` is required
- `user_query` is optional
- if `user_query` is empty, backend synthesizes a default explain-style query

This is already a good anchor + intent split.

## 2. Cluster construction

- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)

Current responsibility:

- resolve seed chapters from `term`
- expand through graph edges
- load chapters
- build evidence

This is the retrieval backbone.

## 3. Retrieval quality evaluation

- [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)

Current responsibility:

- classify retrieval into:
  - `normal`
  - `broad_blocked`
  - `broad_allowed`

This is already a policy gate.

## 4. Narrower-term candidate generation

- [term_recommender.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_recommender.py)

Current responsibility:

- produce narrower follow-up terms from a broad term + precise query

This is currently rule-based and corpus-aware.

## 5. Candidate-anchor evaluation

- [candidate_anchor.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/candidate_anchor.py)

Current responsibility:

- cheaply probe candidate terms against the real retrieval path
- rerank candidates by actual retrieval focus

This is the bridge between semantic recommendation and actual system behavior.

## 6. LLM answer generation

- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py)
- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)

Current responsibility:

- choose answer path
- optionally downgrade answer mode
- build prompt
- call provider

## If This Becomes Part Of Agent Flow

The clean way to think about the term path is:

- not as one giant `/ask` endpoint
- but as a sequence of small callable capabilities

That means the next abstraction step is not “add agents”.
It is:

- extract stable tool interfaces
- make them composable

## Tool Boundaries To Preserve

## Tool A: cluster builder

Suggested abstract interface:

```python
def build_term_cluster(
    *,
    term: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> dict[str, object]:
    ...
```

Output:

- cluster
- evidence
- constraints

This should remain the retrieval tool.

## Tool B: retrieval quality gate

Suggested abstract interface:

```python
def evaluate_term_retrieval(
    *,
    term: str,
    user_query: str,
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
) -> dict[str, object] | None:
    ...
```

Output:

- `None`
- or structured blocked/allowed state

This should remain the decision gate.

## Tool C: narrower-term candidate generator

Suggested abstract interface:

```python
def generate_narrower_term_candidates(
    *,
    broad_term: str,
    user_query: str,
) -> dict[str, object]:
    ...
```

Output:

- `suggested_terms`
- `reason`
- `source`
- `confidence`

This should remain the candidate generator.

## Tool D: candidate-anchor reranker

Suggested abstract interface:

```python
def rerank_term_candidates(
    *,
    terms: list[str],
    user_query: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> list[dict[str, object]]:
    ...
```

Output:

- ranked candidates
- expected response state
- focus metadata

This should remain the retrieval-aware ranker.

## Tool E: answer-mode selector

Suggested abstract interface:

```python
def choose_term_answer_mode(
    *,
    retrieval_state: dict[str, object] | None,
    ranked_candidates: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    ...
```

Output:

- `mode = normal_answer`
- `mode = broad_overview`
- `mode = needs_narrower_term`

This is a policy tool, not a retrieval tool.

## Tool F: answer generator

Suggested abstract interface:

```python
def answer_term_query(
    *,
    user_query: str,
    term: str,
    cluster: dict[str, object],
    mode: str,
) -> dict[str, object]:
    ...
```

Output:

- `answer_markdown`
- citations
- optional LLM metadata

This is the final generation tool.

## Recommended Next Interface Layer

The next step should be a service layer that sits above the raw modules and below `/ask`.

For example:

- `feature_achievement/ask/term_flow.py`

This file should not invent new logic.
It should orchestrate existing tools.

## Suggested Service-Level Interface

```python
def run_term_flow(
    *,
    term: str,
    user_query: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
    llm_enabled: bool,
    llm_model: str,
    llm_timeout_ms: int,
) -> dict[str, object]:
    ...
```

This service should:

1. build cluster
2. evaluate retrieval quality
3. if blocked:
   - generate narrower candidates
   - rerank candidates
   - return narrowing response
4. if broad-overview:
   - set answer mode
   - call answer generator with downgraded guidance
5. if normal:
   - call answer generator normally

The current router can then call this service instead of embedding every branch itself.

## Suggested Pipeline Shape

As a near-term non-agent pipeline:

```text
term + user_query
-> build_term_cluster
-> evaluate_term_retrieval
-> if blocked:
     -> generate_narrower_term_candidates
     -> rerank_term_candidates
     -> return narrowing response
-> else:
     -> choose_term_answer_mode
     -> answer_term_query
     -> return answer response
```

As a future tool-based agent pipeline:

```text
User asks term question
-> Agent calls build_term_cluster
-> Agent calls evaluate_term_retrieval
-> If blocked:
     -> Agent calls generate_narrower_term_candidates
     -> Agent calls rerank_term_candidates
     -> Agent responds with narrowing guidance
-> Else:
     -> Agent calls choose_term_answer_mode
     -> Agent calls answer_term_query
     -> Agent returns final answer
```

The important point is:

- the future agent does not need new logic first
- it needs callable interfaces around current logic

## What Should Be Refactored Next

If this is being prepared for future agent use, the next refactor should be:

## 1. Extract `term_flow.py`

Move current term orchestration out of:

- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)

Reason:

- router should handle HTTP concerns
- service layer should handle flow orchestration

## 2. Keep module responsibilities narrow

Do not merge these back together:

- retrieval quality
- term recommender
- candidate reranker

Reason:

- each of these is a future tool boundary

## 3. Standardize return contracts

Every module should return structured data with:

- `state`
- `reason`
- `source`
- `confidence`

Where appropriate.

This matters because tool-based orchestration depends on explicit machine-readable outputs.

## 4. Make blocked response assembly a service function

Suggested function:

```python
def build_blocked_term_response(
    *,
    retrieval_warnings: dict[str, object],
    ranked_candidates: list[dict[str, object]],
) -> dict[str, object]:
    ...
```

Reason:

- today this is still partly router assembly
- later the same structure can be returned by a tool-based planner or coordinator

## 5. Keep Redis out of the core flow for now

Redis may later support:

- history
- click feedback
- ranking priors

But it should not become part of the core term decision flow yet.

Current order should remain:

1. tools first
2. orchestration second
3. storage and feedback later

## How This Fits Agent Evolution

If you later move:

- RAG -> ChatBot -> Agent

then the term path already gives you a concrete agent-ready subflow:

- detect whether the request is answerable now
- decide whether to answer or narrow
- propose next-step anchors
- rerank those anchors using system-aware probes

That is much more useful than a vague “agent” concept.

It means the term flow can later become:

- one agent toolchain
- one planner subroutine
- or one guarded execution branch

without rewriting the underlying logic.

## Bottom Line

The current term chain is already a strong candidate for a future agent sub-pipeline.

The next abstraction step should be:

- extract a service-level `term_flow.py`
- keep current modules as tool boundaries
- standardize their I/O contracts

That will give you an agent-ready flow before you actually introduce agent orchestration.
