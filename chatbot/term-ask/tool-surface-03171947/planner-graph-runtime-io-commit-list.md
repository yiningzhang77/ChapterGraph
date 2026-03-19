2026-03-19 15:43

# Planner / Graph Runtime I/O Commit List

This commit list implements [planner-graph-runtime-io-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-ask/tool-surface-03171947/planner-graph-runtime-io-plan.md).

Scope:

- define future runtime I/O contracts only
- do not implement planner loop
- do not implement graph executor
- do not change current `/ask` behavior

## Commit 01

`feat(ask): add typed planner and runtime contract classes`

Status: `completed`

### Scope

Add typed runtime-side contract classes in code.

### Changes

- add `RuntimeRequest`
- add `RuntimeStepInput`
- add `RuntimeStepResult`
- add `RuntimeResult`
- add `PlannerDecision`
- add related literal/status types

### Suggested location

- `feature_achievement/ask/runtime_contracts.py`

### Notes

- keep contracts explicit
- avoid generic `dict[str, object]` wrappers where a named field is clearer

## Commit 02

`feat(ask): expose runtime contracts through runtime surface`

Status: `pending`

### Scope

Extend [runtime_surface.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/runtime_surface.py).

### Changes

- export the new runtime contracts
- keep the surface thin
- do not add runtime behavior

### Goal

Make the future runtime-facing vocabulary importable from one place.

## Commit 03

`test(ask): add focused coverage for planner and runtime contracts`

Status: `pending`

### Scope

Add focused tests for the new runtime contracts and exports.

### Changes

- verify contract classes import cleanly
- verify basic field expectations
- verify runtime surface exports them

### Suggested files

- `tests/test_runtime_contracts.py`
- extend [test_runtime_surface.py](C:/Users/hy/ChapterGraph/tests/test_runtime_surface.py)

## Commit 04

`test(smoke): validate planner/runtime contract introduction is behavior-neutral`

Status: `pending`

### Scope

Run regression validation after contract introduction.

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

1. add contracts
2. export contracts via runtime surface
3. add focused tests
4. run full regression

## Stop Conditions

Stop and reassess if:

- a planner loop starts appearing
- a graph executor starts appearing
- the runtime surface begins dispatching behavior
- `/ask` behavior changes

## Bottom Line

This step is complete when:

- future runtime I/O contracts exist in code
- they are exposed through the runtime-facing surface
- tests and smoke confirm zero product behavior change
