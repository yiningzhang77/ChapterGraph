2026-03-17 20:21

# Typed Flow Result Commit List

This commit list implements [typed-flow-result-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-ask/tool-surface-03171947/typed-flow-result-plan.md).

Scope:

- implement Direction 2 only
- add typed flow result contracts
- make both flows return typed results
- keep router transport-focused
- do not introduce registry/runtime machinery

## Commit 01

`feat(ask): add typed term and chapter flow result contracts`

Status: `completed`

### Scope

Add explicit flow result contracts to [tool_contracts.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/tool_contracts.py).

### Changes

- add `TermFlowResult`
- add `ChapterFlowResult`
- optionally add a small shared base only if it stays obvious

### Notes

- keep fields explicit
- avoid `Any` payload wrappers
- match current flow output shape closely

## Commit 02

`refactor(ask): make term_flow return TermFlowResult`

Status: `completed`

### Scope

Update [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py).

### Changes

- change `run_term_flow(...)` return type to `TermFlowResult`
- replace final dict assembly with typed object construction
- keep current logic unchanged

### Done when

- flow behavior matches current behavior
- only output type changes

## Commit 03

`refactor(ask): make chapter_flow return ChapterFlowResult`

Status: `completed`

### Scope

Update [chapter_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/chapter_flow.py).

### Changes

- change `run_chapter_flow(...)` return type to `ChapterFlowResult`
- replace final dict assembly with typed object construction
- keep current logic unchanged

## Commit 04

`refactor(api): consume typed flow results in ask router`

Status: `completed`

### Scope

Update [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py).

### Changes

- stop treating flow outputs as loose dicts
- read typed result attributes directly
- remove or simplify dict coercion helpers
- keep HTTP response model unchanged

### Boundary

Router should still only do:

- request parsing
- flow dispatch
- response shaping

## Commit 05

`test(ask): add focused coverage for typed flow results`

Status: `pending`

### Scope

Add or update tests.

### Changes

- verify `run_term_flow(...)` returns `TermFlowResult`
- verify `run_chapter_flow(...)` returns `ChapterFlowResult`
- verify router still shapes the same API response

### Suggested files

- [test_term_flow.py](C:/Users/hy/ChapterGraph/tests/test_term_flow.py)
- [test_chapter_flow.py](C:/Users/hy/ChapterGraph/tests/test_chapter_flow.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

## Commit 06

`test(smoke): validate typed flow result refactor`

Status: `pending`

### Scope

Run regression validation after the refactor.

### Validation

```powershell
python -m pytest -q tests/test_term_flow.py tests/test_chapter_flow.py tests/test_ask_api.py
python -m feature_achievement.scripts.smoke_ask
python -m feature_achievement.scripts.smoke_ask_cluster
python -m pytest -q
```

### Done when

- tests pass
- smoke passes
- response behavior is unchanged

## Recommended Order

1. contracts
2. term flow
3. chapter flow
4. router
5. focused tests
6. smoke validation

## Stop Conditions

Stop and reassess if:

- router starts duplicating flow logic
- contracts become too generic to be useful
- response behavior drifts from current `/ask`

## Bottom Line

This refactor is complete when:

- flows return typed contracts
- router consumes typed contracts
- no product-facing behavior changes
