# Candidate Anchor Commit List

This document turns [candidate-anchor-plan.md](C:/Users/hy/ChapterGraph/chatbot/term-narrowing/candidate-anchor-plan.md) into an implementation sequence.

Goal:

- probe suggested narrower terms against the current retrieval pipeline
- rank suggested terms by actual retrieval focus instead of semantic guess alone
- keep the evaluator cheap and LLM-free
- improve blocked-term retry quality before adding Redis

This series must not redesign `/ask`.
It adds a retrieval-aware ranking layer on top of:

- `term_recommender.py`
- `retrieval_quality.py`

## Commit 01

### `feat(ask): add candidate-anchor evaluator module`

Status: `completed`

### Scope

Files:
- add [candidate_anchor.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/candidate_anchor.py)
- add focused tests, likely [test_candidate_anchor.py](C:/Users/hy/ChapterGraph/tests/test_candidate_anchor.py)

### Changes

Create a dedicated evaluator module with a clear interface.

Suggested shape:

```python
def evaluate_candidate_anchor(
    *,
    term: str,
    user_query: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> dict[str, object]:
    ...
```

And a batch helper:

```python
def rank_candidate_anchors(
    *,
    terms: list[str],
    user_query: str,
    run_id: int,
    enrichment_version: str,
    session: Session,
) -> list[dict[str, object]]:
    ...
```

The evaluator should:

- build a temporary term request
- call current retrieval logic
- inspect cluster/evidence spread
- classify the expected response state

Do not call the LLM.

### Tests

Add unit tests for:

1. focused candidate -> `expected_response_state = normal`
2. still-broad candidate -> `expected_response_state = needs_narrower_term`
3. no-seed candidate -> `expected_response_state = no_seed`

### Done when

- candidate probing exists as a standalone module
- the evaluator is cheap and LLM-free

## Commit 02

### `refactor(ask): reuse build_cluster and retrieval-quality logic inside candidate evaluator`

Status: `completed`

### Scope

Files:
- [candidate_anchor.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/candidate_anchor.py)
- [test_candidate_anchor.py](C:/Users/hy/ChapterGraph/tests/test_candidate_anchor.py)

### Changes

Avoid inventing a second retrieval approximation layer.

The evaluator should reuse:

- `build_cluster(...)`
- `evaluate_term_retrieval_quality(...)`

The evaluator should act as orchestration over existing logic, not a parallel implementation.

### Tests

Add/update tests to assert:

1. evaluator passes candidate term through current cluster builder path
2. evaluator derives expected state from current retrieval-quality rules
3. evaluator remains independent from prompt/LLM code

### Done when

- evaluator is grounded in the actual `/ask` retrieval path

## Commit 03

### `feat(ask): add ranking heuristic for candidate terms`

Status: `completed`

### Scope

Files:
- [candidate_anchor.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/candidate_anchor.py)
- [test_candidate_anchor.py](C:/Users/hy/ChapterGraph/tests/test_candidate_anchor.py)

### Changes

Rank candidates with a simple first-pass heuristic:

1. `expected_response_state = normal`
2. lower `seed_count`
3. lower `evidence_book_count`
4. lower `evidence_chapter_count`
5. blocked candidates later
6. no-seed candidates last

Suggested output item shape:

```json
{
  "term": "data persistence",
  "focus_state": "focused",
  "expected_response_state": "normal",
  "seed_count": 3,
  "evidence_chapter_count": 3,
  "evidence_book_count": 1,
  "source": "retrieval_probe"
}
```

### Tests

Add/update tests for:

1. focused candidate ranks above broad candidate
2. no-seed candidate ranks last
3. ordering is stable and deterministic

### Done when

- the evaluator can return a retrieval-aware ordering of candidate terms

## Commit 04

### `feat(api): rerank blocked-term suggested_terms with candidate evaluator`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

When a broad term is blocked:

1. generate candidate terms from `term_recommender.py`
2. rerank them through `candidate_anchor.py`
3. return `suggested_terms` in reranked order

Keep the existing recommendation metadata.

Do not break the current blocked-response contract.

### Tests

Add/update tests for:

1. blocked response returns reranked `suggested_terms`
2. broad candidate is not placed first when a more focused one exists
3. fallback still works if candidate evaluation is unavailable

### Done when

- blocked-term suggestions are ordered by actual retrieval behavior

## Commit 05

### `feat(api): expose optional suggested-term diagnostics`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

Add optional diagnostics to the blocked-response metadata.

Suggested shape:

```json
{
  "suggested_term_diagnostics": [
    {
      "term": "data persistence",
      "expected_response_state": "normal",
      "focus_state": "focused"
    },
    {
      "term": "Spring Data",
      "expected_response_state": "needs_narrower_term",
      "focus_state": "broad"
    }
  ]
}
```

Frontend may ignore this at first.
The primary goal is observability and future tool compatibility.

### Tests

Add/update tests for:

1. diagnostics exist in blocked response
2. diagnostics align with reranked order
3. clean responses do not include diagnostics

### Done when

- the backend exposes enough retrieval-aware metadata for later UI or tool use

## Commit 06

### `test(smoke): validate real-DB candidate-anchor reranking`

Status: `completed`

### Scope

Files:
- [smoke_ask.py](C:/Users/hy/ChapterGraph/feature_achievement/scripts/smoke_ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

Add a smoke path that validates real-DB reranking behavior for a blocked term.

Suggested scenario:

1. send:
   - `term=Spring`
   - `user_query=How does Spring implement data persistence?`
2. verify blocked state
3. inspect reranked suggestions
4. verify a more focused term ranks above a still-broad one

Current real-DB expectation:

- `data persistence` or `JdbcTemplate` should rank above `Spring Data`

### Validation commands

```powershell
python -m pytest -q tests/test_candidate_anchor.py tests/test_ask_api.py
python -m feature_achievement.scripts.smoke_ask
python -m pytest -q
```

### Done when

- candidate reranking is validated against the current real database

## Execution Notes

### Order matters

Implement in this order:

1. standalone candidate evaluator
2. reuse current retrieval path
3. add ranking heuristic
4. rerank blocked suggestions in API
5. expose optional diagnostics
6. validate against the real DB

Reason:

- the evaluator must be grounded in real retrieval before the API can depend on it
- diagnostics are secondary to correct ranking

### Architecture principle

Keep roles separate:

- recommender generates candidates
- candidate-anchor evaluator ranks them
- retrieval-quality evaluator decides blocked/allowed

This separation keeps future model-assisted upgrades possible without rewriting `/ask`.

### Non-goals

Do not include these in the same series:

- Redis feedback storage
- LLM-based recommendation ranking
- semantic query rewriting
- automatic term replacement without user confirmation
- full agent orchestration
