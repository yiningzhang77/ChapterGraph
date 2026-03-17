2026-03-17 16:37

# Agent Tool Interface Commit List

This document turns [agent-tool-interface-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-ask/agent-tool-interface-plan.md) into an implementation sequence.

Goal:

- define capability-level tool contracts under `term_flow.py`
- keep current `/ask` term behavior unchanged
- make the term pipeline easier to evolve into a future agent-executed flow

This is not an agent runtime project.
It is an interface-tightening project.

## Commit 01

### `feat(ask): add typed result contracts for term tool capabilities`

Status: `completed`

### Scope

Files:
- add `feature_achievement/ask/tool_contracts.py` or equivalent

### Changes

Add typed result contracts for the capability layer.

Recommended contracts:

- `ClusterToolResult`
- `RetrievalQualityToolResult`
- `NarrowingRecommendationToolResult`
- `CandidateAnchorDiagnostic`
- `CandidateAnchorRankingToolResult`
- `TermAnswerToolResult`

Use dataclasses or strict typed models.

Do not add runtime registry logic yet.

### Done when

- capability outputs have a stable typed shape
- result contracts are centralized in one place

## Commit 02

### `feat(ask): add cluster and retrieval-quality tool wrappers`

Status: `pending`

### Scope

Files:
- add `feature_achievement/ask/term_tools.py` or equivalent
- possibly small imports in existing ask modules

### Changes

Add interface-level wrapper functions for:

- `build_term_cluster_tool(...)`
- `evaluate_term_retrieval_quality_tool(...)`

Initially these wrappers can call:

- existing cluster builder logic
- existing retrieval-quality logic

But they must return typed contract objects from Commit 01.

### Done when

- cluster and retrieval-quality capabilities are callable through typed wrappers
- wrappers do not change current behavior

## Commit 03

### `feat(ask): add narrowing and candidate-anchor tool wrappers`

Status: `pending`

### Scope

Files:
- `feature_achievement/ask/term_tools.py`
- related imports if needed

### Changes

Add typed wrapper functions for:

- `recommend_narrower_terms_tool(...)`
- `rank_candidate_anchors_tool(...)`

These should wrap:

- `term_recommender.py`
- `candidate_anchor.py`

The wrapper layer should preserve:

- recommendation reason
- recommendation source
- recommendation confidence
- rerank diagnostics

### Done when

- recommendation and candidate evaluation capabilities are exposed through typed wrappers
- typed results preserve current metadata

## Commit 04

### `feat(ask): add term answer generation tool wrapper`

Status: `pending`

### Scope

Files:
- `feature_achievement/ask/term_tools.py`
- imports into LLM modules if needed

### Changes

Add:

- `generate_term_answer_tool(...)`

This wrapper should:

- accept term, user query, cluster, response mode, response guidance
- call the current prompt + LLM path
- return `TermAnswerToolResult`

It should not decide whether the request is blocked.
It only generates answers once orchestration has already decided to answer.

### Done when

- answer generation is behind a capability wrapper with a typed result

## Commit 05

### `refactor(ask): move term_flow.py onto capability tool interfaces`

Status: `pending`

### Scope

Files:
- [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py)

### Changes

Update `term_flow.py` so it depends on the wrapper layer rather than calling low-level modules directly.

After this commit, `term_flow.py` should read like orchestration:

1. build cluster
2. evaluate retrieval quality
3. maybe recommend narrower terms
4. maybe rerank candidates
5. maybe generate overview answer
6. maybe generate normal answer

The flow order must not change.
Only the dependency boundary changes.

### Done when

- `term_flow.py` orchestrates capability wrappers instead of low-level internals
- external `/ask` behavior remains unchanged

## Commit 06

### `refactor(api): keep router and response shaping unchanged while term interfaces tighten`

Status: `pending`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)

### Changes

Confirm the router still does only:

- request parsing
- term/chapter branching
- response shaping

Do not let router logic re-expand because of the new interface layer.

If needed, clean imports or intermediate payload handling so the router remains thin.

### Done when

- router remains transport-focused
- term logic stays inside `term_flow.py`

## Commit 07

### `test(ask): cover capability wrappers and term_flow behavior preservation`

Status: `pending`

### Scope

Files:
- add tests for wrapper result contracts
- add/update tests around `term_flow.py`

### Changes

Cover at least:

1. cluster tool returns typed contract
2. retrieval-quality tool returns expected typed state
3. recommender tool preserves recommendation metadata
4. candidate-anchor tool preserves diagnostics
5. answer tool returns typed answer result
6. `term_flow.py` still preserves:
   - normal
   - broad_overview
   - needs_narrower_term

### Done when

- tool wrappers are covered
- `term_flow.py` behavior remains locked by tests

## Commit 08

### `test(smoke): validate typed tool-interface term flow against current real db`

Status: `pending`

### Scope

Files:
- no mandatory code change

### Changes

Run current smoke validation after the interface refactor:

```powershell
python -m pytest -q
python -m feature_achievement.scripts.smoke_ask
python -m feature_achievement.scripts.smoke_ask_cluster
```

The point is to verify:

- typed interface refactor did not alter term behavior
- blocked recommendation path still works
- overview path still works
- normal answer path still works

### Done when

- smoke still passes against the current DB
- term flow remains behaviorally stable after interface tightening

## Execution Notes

### Order matters

Implement in this order:

1. contracts
2. cluster/quality wrappers
3. narrowing/rerank wrappers
4. answer wrapper
5. migrate `term_flow.py`
6. confirm router stays thin
7. add focused tests
8. run smoke

Reason:

- contracts should exist before wrappers
- wrappers should exist before flow migration
- flow migration should happen before any smoke validation

### Non-goals

Do not introduce yet:

- a generic tool registry
- cross-flow abstraction for chapter mode
- agent planner runtime
- LangGraph-style node execution
- Redis or persistence changes

Those may come later, but this commit series is only about interface shape.

## Bottom Line

At the end of this series:

- `term_flow.py` remains orchestration
- capability steps are exposed through typed tool wrappers
- the term path becomes structurally agent-ready
- `/ask` behavior should remain unchanged
