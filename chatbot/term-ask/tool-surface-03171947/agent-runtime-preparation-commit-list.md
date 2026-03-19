2026-03-17 20:29

# Agent Runtime Preparation Commit List

This commit list implements [agent-runtime-preparation-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-ask/tool-surface-03171947/agent-runtime-preparation-plan.md).

Scope:

- prepare the current `/ask` structure for a future agent runtime
- keep runtime preparation at interface level
- avoid planner/loop/registry framework work
- preserve current product behavior

## Commit 01

`docs(ask): define runtime-callable flow and tool surfaces`

Status: `completed`

### Scope

Make the runtime-callable boundaries explicit in code/docs.

### Changes

- identify flow-level runtime-callable entrypoints
  - `run_term_flow(...)`
  - `run_chapter_flow(...)`
- identify tool-level runtime-callable entrypoints
  - exports from [tools.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/tools.py)
- explicitly note what is not runtime-callable
  - router
  - low-level internal helpers

### Notes

- this is boundary work
- not runtime behavior work

## Commit 02

`feat(ask): add thin runtime-facing surface module`

Status: `completed`

### Scope

Add a small explicit runtime-facing module, for example:

- `feature_achievement/ask/runtime_surface.py`

### Changes

- export flow-level entrypoints
- export tool-level entrypoints
- keep it as a thin surface only

### Boundary

Do not:

- add planner logic
- add dispatch-by-string logic
- add state machine logic

## Commit 03

`refactor(ask): centralize runtime-facing state semantics`

Status: `pending`

### Scope

Make business/runtime states more explicit outside router behavior.

### Changes

- keep state names stable
  - `normal`
  - `broad_overview`
  - `needs_narrower_term`
- ensure these remain visible from typed flow results
- avoid encoding runtime meaning only in HTTP-layer behavior

### Goal

Prepare flow outputs for future non-HTTP callers.

## Commit 04

`test(ask): add focused coverage for runtime-facing surface exports`

Status: `pending`

### Scope

Add small tests for the new runtime-facing surface.

### Changes

- verify runtime-facing module exports the intended flows
- verify runtime-facing module exports the intended tools
- verify no behavior change is introduced

### Suggested files

- a new `tests/test_runtime_surface.py`
- optionally extend [test_tools_surface.py](C:/Users/hy/ChapterGraph/tests/test_tools_surface.py)

## Commit 05

`test(smoke): validate runtime preparation refactor`

Status: `pending`

### Scope

Run regression validation after the preparation step.

### Validation

```powershell
python -m pytest -q
python -m feature_achievement.scripts.smoke_ask
python -m feature_achievement.scripts.smoke_ask_cluster
```

### Done when

- tests pass
- smoke passes
- `/ask` behavior is unchanged

## Recommended Order

1. define runtime-callable boundary
2. add thin runtime surface
3. stabilize runtime-facing states
4. add focused export coverage
5. run full regression

## Stop Conditions

Stop and reassess if:

- a planner starts appearing
- dispatch logic becomes dynamic without a real use
- runtime surface starts duplicating flow orchestration
- router behavior changes for product reasons

## Bottom Line

This preparation work is complete when:

- there is a clear runtime seam
- a thin runtime-facing surface exists
- flow and tool boundaries remain intact
- no agent runtime machinery has been added prematurely
