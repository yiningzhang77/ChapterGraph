2026-03-19 19:16

# Reaching Runtime State Commit List

This commit list implements [reaching-runtime-state.md](C:/Users/hy/ChapterGraph/runtime-03191902/reaching-runtime-state.md).

Scope:

- move `/ask` toward a real runtime-backed architecture
- implement the runtime shell first
- do not implement planner logic
- do not implement graph executor yet
- preserve current `/ask` behavior

## Commit 01

`feat(ask): add thin runtime shell entrypoint`

Status: `completed`

### Scope

Add a runtime entry module, for example:

- `feature_achievement/ask/runtime.py`

### Changes

- add `run_runtime(request: RuntimeRequest, session: Session) -> RuntimeResult`
- first version dispatches deterministically by `query_type`
- term path wraps `run_term_flow(...)`
- chapter path wraps `run_chapter_flow(...)`

### Boundary

Do not:

- add step graph execution yet
- add planner logic
- add retries or loops

This is only the runtime shell.

## Commit 02

`feat(ask): add flow-result to RuntimeResult adapters`

Status: `completed`

### Scope

Convert typed flow results into runtime execution results.

### Changes

- add small helpers to map:
  - `TermFlowResult -> RuntimeResult`
  - `ChapterFlowResult -> RuntimeResult`
- keep runtime status explicit
- keep business state mapping explicit

### Goal

Make the runtime shell return one normalized execution result type.

## Commit 03

`refactor(api): route /ask through runtime adapter and runtime shell`

Status: `completed`

### Scope

Update [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py).

### Changes

- convert `AskRequest -> RuntimeRequest` via [runtime_adapter.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/runtime_adapter.py)
- call `run_runtime(...)` instead of calling flows directly
- shape HTTP response from `RuntimeResult`

### Constraint

Keep the external `/ask` response unchanged.

## Commit 04

`test(ask): add focused coverage for runtime-backed ask path`

Status: `completed`

### Scope

Add focused tests for the new runtime shell and router wiring.

### Changes

- verify `run_runtime(...)` dispatches term requests correctly
- verify `run_runtime(...)` dispatches chapter requests correctly
- verify router now depends on runtime path, not direct flow calls

### Suggested files

- `tests/test_runtime.py`
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

## Commit 05

`test(smoke): validate runtime-backed /ask shell`

Status: `completed`

### Scope

Run behavior regression after the runtime shell is inserted.

### Validation

```powershell
python -m pytest -q
python -m feature_achievement.scripts.smoke_ask
python -m feature_achievement.scripts.smoke_ask_cluster
```

### Done when

- tests pass
- smoke passes
- `/ask` still behaves the same
- runtime shell is now the main execution entrypoint

## Recommended Order

1. runtime shell
2. flow-to-runtime adapters
3. router wiring
4. focused tests
5. smoke regression

## Stop Conditions

Stop and reassess if:

- runtime shell starts embedding planner logic
- router starts duplicating runtime logic
- runtime result shape becomes transport-specific
- behavior drifts from current `/ask`

## Bottom Line

This step is complete when:

- `/ask` executes through `RuntimeRequest -> run_runtime(...) -> RuntimeResult`
- router no longer calls flows directly
- behavior remains unchanged

## Validation

```powershell
python -m pytest -q
python -m feature_achievement.scripts.smoke_ask
python -m feature_achievement.scripts.smoke_ask_cluster
```

Latest result:

- `124 passed`
- `smoke_ask passed`
- `smoke_ask_cluster passed`
