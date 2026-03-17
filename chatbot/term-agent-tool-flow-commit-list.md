2026-03-17 14:30

# Term Agent Tool Flow Commit List

This document turns [term-agent-tool-flow-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-agent-tool-flow-plan.md) into an implementation sequence.

Goal:

- extract term-mode orchestration out of the router
- introduce a service-level `term_flow.py`
- preserve current modules as future tool boundaries
- keep current `/ask` behavior stable while making the flow more agent-ready

This series is structural first.
It should not redesign retrieval, recommendation, reranking, or LLM behavior.

## Commit 01

### `feat(ask): add term_flow service module skeleton`

Status: `completed`

### Scope

Files:
- add [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py)
- optionally update [__init__.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/__init__.py)

### Changes

Create the new service module and define the main entry point:

```python
def run_term_flow(
    *,
    req: AskRequest,
    session: Session,
) -> dict[str, object]:
    ...
```

In this first commit, the function can be a thin shell with clearly named internal helpers.

Suggested internal helper layout:

```python
def _build_term_cluster(...)
def _evaluate_term_quality(...)
def _build_narrowing_payload(...)
def _generate_term_answer(...)
```

### Done when

- `term_flow.py` exists
- the future orchestration boundary is explicit

## Commit 02

### `refactor(ask): move cluster and retrieval-quality orchestration into term_flow`

Status: `completed`

### Scope

Files:
- [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py)
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- tests touching router behavior as needed

### Changes

Move these term-path steps out of the router:

1. cluster construction
2. evidence extraction
3. retrieval-quality evaluation

The router should stop owning these branches directly.

The service should return a structured internal result such as:

```json
{
  "cluster_payload": {...},
  "evidence": {...},
  "retrieval_warnings": {...},
  "response_state": "needs_narrower_term"
}
```

### Done when

- router no longer directly orchestrates retrieval quality for term mode
- term flow owns the retrieval path up to state classification

## Commit 03

### `refactor(ask): move narrowing generation and candidate reranking into term_flow`

Status: `completed`

### Scope

Files:
- [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py)
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

Move these term-path steps into the service:

1. `recommend_narrower_terms(...)`
2. `rank_candidate_anchors(...)`
3. recommendation metadata assembly
4. `suggested_term_diagnostics` assembly

The router should receive already assembled narrowing payloads from the service.

### Done when

- blocked-term recommendation logic is fully owned by `term_flow.py`
- router stops managing candidate reranking directly

## Commit 04

### `refactor(ask): move answer-mode selection and LLM call into term_flow`

Status: `pending`

### Scope

Files:
- [term_flow.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_flow.py)
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)
- [test_qwen_prompts.py](C:/Users/hy/ChapterGraph/tests/test_qwen_prompts.py) if needed

### Changes

Move these remaining term-path steps into the service:

1. decide:
   - `normal`
   - `broad_overview`
   - `needs_narrower_term`
2. build `response_guidance`
3. call `ask_qwen(...)` if allowed
4. capture `llm_error`

The router should not decide whether term mode should answer or block.

### Done when

- `term_flow.py` owns end-to-end term-mode execution
- router no longer contains term answer policy logic

## Commit 05

### `refactor(api): keep router focused on request/response shaping`

Status: `pending`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

After term flow is extracted, shrink router responsibility to:

1. accept `AskRequest`
2. branch:
   - term -> `run_term_flow(...)`
   - chapter -> existing path for now
3. build `graph_fragment`
4. shape `AskResponse`

The router should remain the HTTP adapter, not the orchestration layer.

### Done when

- router code is materially thinner
- term flow is no longer embedded across multiple router branches

## Commit 06

### `test(ask): validate term_flow preserves current API behavior`

Status: `pending`

### Scope

Files:
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)
- optionally add [test_term_flow.py](C:/Users/hy/ChapterGraph/tests/test_term_flow.py)

### Changes

Add service-level tests and confirm existing API behavior is unchanged.

Cases to validate:

1. clean term -> normal answer path
2. broad precise term -> blocked path
3. broad definition term -> broad overview path
4. rerank failure -> fallback suggestion order
5. LLM error -> preserved in meta

This commit is about behavior preservation, not new features.

### Done when

- `term_flow.py` is covered directly
- existing `/ask` term tests still pass

## Commit 07

### `test(smoke): validate term_flow against current real DB`

Status: `pending`

### Scope

Files:
- [smoke_ask.py](C:/Users/hy/ChapterGraph/feature_achievement/scripts/smoke_ask.py)
- optionally add a dedicated term-flow smoke script later if needed

### Changes

Use the existing smoke path to verify that term-mode behavior is unchanged after the refactor.

At minimum revalidate:

1. normal term
2. broad blocked term
3. broad overview term
4. narrowed retry path

### Validation commands

```powershell
python -m pytest -q tests/test_term_flow.py tests/test_ask_api.py
python -m feature_achievement.scripts.smoke_ask
python -m pytest -q
```

### Done when

- the extracted service behaves the same as the pre-refactor term path on the current DB

## Execution Notes

### Order matters

Implement in this order:

1. create `term_flow.py`
2. move retrieval orchestration
3. move narrowing orchestration
4. move answer orchestration
5. thin the router
6. preserve behavior with tests
7. validate against the real DB

Reason:

- the service boundary has to exist before logic can migrate into it
- router thinning should happen after the service has real coverage

### Architecture principle

Keep these future tool boundaries separate:

- cluster builder
- retrieval quality evaluator
- term recommender
- candidate-anchor evaluator
- answer generator

`term_flow.py` should orchestrate them, not absorb their responsibilities.

### Non-goals

Do not mix this series with:

- chapter flow extraction
- Redis
- agent runtime/framework adoption
- memory/persistence
- hit highlight work

## Bottom Line

The immediate structural next step is:

- extract `term_flow.py`
- move term execution policy into it
- keep router as the HTTP adapter

That gives you an agent-ready service boundary without changing the product behavior first.
