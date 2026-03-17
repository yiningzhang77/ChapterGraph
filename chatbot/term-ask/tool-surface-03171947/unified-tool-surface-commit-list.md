2026-03-17 19:47

# Unified Tool Surface Commit List

This document turns [unified-tool-surface-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-ask/tool-surface-03171947/unified-tool-surface-plan.md) into an implementation sequence.

Goal:

- add one thin shared tool surface for `/ask`
- keep `term_tools.py` and `chapter_tools.py` as concrete capability modules
- rewire flows to depend on the unified surface
- avoid adding runtime registry complexity too early

This is a structure cleanup step, not an agent runtime step.

## Commit 01

### `feat(ask): add unified ask tool surface module`

Status: `completed`

### Scope

Files:
- add `feature_achievement/ask/tools.py`

### Changes

Create one shared tool surface module that explicitly exports:

- `build_term_cluster_tool`
- `evaluate_term_retrieval_quality_tool`
- `recommend_narrower_terms_tool`
- `rank_candidate_anchors_tool`
- `generate_term_answer_tool`
- `build_chapter_cluster_tool`
- `generate_chapter_answer_tool`

First pass should be thin:

- explicit imports
- explicit exports
- no registry object yet

### Done when

- one shared tool surface exists
- callers can import capability tools from one place

## Commit 02

### `refactor(ask): switch term_flow.py to unified tool surface imports`

Status: `completed`

### Scope

Files:
- [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py)

### Changes

Update `term_flow.py` so it imports capability tools from:

- `feature_achievement.ask.tools`

instead of:

- `term_tools.py`

No behavior change.

### Done when

- `term_flow.py` depends on the unified surface
- term flow tests still pass

## Commit 03

### `refactor(ask): switch chapter_flow.py to unified tool surface imports`

Status: `completed`

### Scope

Files:
- [chapter_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/chapter_flow.py)

### Changes

Update `chapter_flow.py` so it imports capability tools from:

- `feature_achievement.ask.tools`

instead of:

- `chapter_tools.py`

No behavior change.

### Done when

- `chapter_flow.py` depends on the unified surface
- chapter flow tests still pass

## Commit 04

### `test(ask): add focused coverage for unified tool surface exports`

Status: `completed`

### Scope

Files:
- add `tests/test_tools_surface.py`

### Changes

Add a small focused test that verifies:

1. expected tool names are exported
2. imports resolve cleanly
3. term/chapter flows can still use the surface without changing behavior

Do not overdesign this into registry tests.

### Done when

- unified surface exports are directly covered

## Commit 05

### `test(smoke): validate unified tool surface refactor preserves ask behavior`

Status: `pending`

### Scope

Files:
- no mandatory code change

### Changes

Run:

```powershell
python -m pytest -q
python -m feature_achievement.scripts.smoke_ask
python -m feature_achievement.scripts.smoke_ask_cluster
```

Goal:

- confirm the surface refactor did not change behavior
- confirm term and chapter paths both still work

### Done when

- tests and smoke still pass

## Optional Commit 06

### `feat(ask): add static AVAILABLE_ASK_TOOLS inventory`

Status: `pending`

### Scope

Files:
- `feature_achievement/ask/tools.py`

### Changes

If there is a concrete need, add a static inventory such as:

```python
AVAILABLE_ASK_TOOLS = {
    "build_term_cluster": build_term_cluster_tool,
    "evaluate_term_retrieval_quality": evaluate_term_retrieval_quality_tool,
    "recommend_narrower_terms": recommend_narrower_terms_tool,
    "rank_candidate_anchors": rank_candidate_anchors_tool,
    "generate_term_answer": generate_term_answer_tool,
    "build_chapter_cluster": build_chapter_cluster_tool,
    "generate_chapter_answer": generate_chapter_answer_tool,
}
```

Do this only if it will be used immediately by the next step.

### Done when

- there is an explicit static inventory
- no dynamic registry behavior has been introduced

## Execution Notes

### Order matters

Implement in this order:

1. create the surface
2. migrate term flow
3. migrate chapter flow
4. add focused export test
5. run smoke
6. only then consider optional inventory

Reason:

- the surface must exist before flows can depend on it
- tests should validate the actual final import path
- inventory should only be added after the surface proves stable

### Non-goals

Do not introduce:

- dynamic string-based dispatch
- generic tool registry runtime
- planner execution
- agent state
- shared metadata protocol

Those belong to a later stage.

## Bottom Line

This commit series should end with:

- one shared ask tool surface
- both flows importing from it
- tests and smoke unchanged
- no unnecessary registry machinery
