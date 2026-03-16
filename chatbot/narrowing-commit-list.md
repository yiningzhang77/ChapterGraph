# Narrowing Commit List

This document turns [narrowing-plan.md](C:/Users/hy/ChapterGraph/chatbot/narrowing-plan.md) into an implementation sequence.

Goal:

- recommend concrete narrower follow-up terms when a broad term is blocked
- keep the first version rule-based
- expose the capability behind a clear interface
- let the frontend turn recommendations into a usable next step
- keep Redis optional and secondary

This series must not redesign `/ask`.
It should add a replaceable narrowing module on top of the current robust term flow.

## Commit 01

### `feat(ask): extract rule-based term recommender module`

Status: `completed`

### Scope

Files:
- add [term_recommender.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/term_recommender.py)
- add focused tests, likely in [test_term_recommender.py](C:/Users/hy/ChapterGraph/tests/test_term_recommender.py)

### Changes

Create a dedicated recommender module with a clear interface, for example:

```python
def recommend_narrower_terms(
    *,
    broad_term: str,
    user_query: str,
) -> dict[str, object]:
    ...
```

First-pass implementation should be rule-based and corpus-aware.

Suggested shape:

```python
BROAD_TERM_RULES = {
    "spring": [...],
    "data": [...],
    "security": [...],
}
```

Return structured output such as:

```json
{
  "reason": "spring_persistence",
  "suggested_terms": [
    "Spring Data",
    "data persistence",
    "JdbcTemplate",
    "Spring Data JPA"
  ],
  "source": "rule_based",
  "confidence": "heuristic"
}
```

### Tests

Add tests for:

1. `Spring` + persistence query
2. `Spring` + web query
3. `Spring` + security query
4. unmatched broad term fallback
5. unmatched query fallback

### Done when

- recommendation logic exists outside `retrieval_quality.py`
- the recommender has a stable structured contract

## Commit 02

### `refactor(ask): move blocked-term suggestions to term recommender`

Status: `completed`

### Scope

Files:
- [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_retrieval_quality.py](C:/Users/hy/ChapterGraph/tests/test_retrieval_quality.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

Keep `retrieval_quality.py` focused on:

- normal
- broad_blocked
- broad_allowed

Do not let it own corpus-specific recommendation rules.

Wire the recommender into the blocked broad-term response path so that:

- `meta.retrieval_warnings.suggested_terms` comes from `term_recommender.py`
- optional recommendation metadata such as `reason`, `source`, `confidence` can be attached

Recommended split:

- `retrieval_quality.py` decides whether narrowing is needed
- `term_recommender.py` decides what narrower terms to suggest

### Tests

Update API tests to assert:

1. blocked broad request returns recommender-derived suggestions
2. allowed broad overview may also include recommender-derived follow-up suggestions
3. clean retrieval path still has no recommendation warning

### Done when

- suggestion ownership is moved out of `retrieval_quality.py`
- backend broad-blocked responses use the new recommender output

## Commit 03

### `feat(api): include recommendation metadata in blocked responses`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/schemas/ask.py) only if response schema needs extension
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

Expand blocked-response metadata so the frontend receives more than just a plain list.

Suggested shape:

```json
{
  "meta": {
    "response_state": "needs_narrower_term",
    "retrieval_warnings": {
      "state": "broad_blocked",
      "message": "...",
      "suggested_terms": [...],
      "recommendation_reason": "spring_persistence",
      "recommendation_source": "rule_based",
      "recommendation_confidence": "heuristic"
    }
  }
}
```

Keep this additive.
Do not break the current broad-term contract.

### Tests

Add/update tests for:

1. recommendation metadata present in blocked response
2. fallback recommendation metadata present for unmatched cases
3. no recommendation metadata for non-blocked clean requests

### Done when

- the frontend has enough structured data to render useful narrowing guidance

## Commit 04

### `feat(frontend): make blocked-term suggestions clickable`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- [index.html](C:/Users/hy/ChapterGraph/frontend/index.html)

### Changes

Turn suggested-term chips into interactive controls.

First version behavior:

1. user clicks a suggested term
2. `Term` input is replaced with that term
3. existing `user_query` stays unchanged
4. no auto-submit

Reason:

- user keeps control
- no surprise request is sent automatically

Optional UI copy:

- `Suggested narrower terms`
- `Click one to refine the term input`

### Done when

- blocked-term suggestions are actionable instead of passive text

## Commit 05

### `feat(frontend): add narrowed-term interaction hint`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- [index.html](C:/Users/hy/ChapterGraph/frontend/index.html)

### Changes

After a suggestion click, show a small non-modal hint such as:

- `Term updated to Spring Data. Review the question and send again.`

Do not overcomplicate this.
This is just a UX bridge between blocked response and retry.

### Done when

- users can tell that the click updated the input intentionally

## Commit 06

### `test(smoke): validate blocked-term narrowing retry flow`

Status: `pending`

### Scope

Files:
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)
- [smoke_ask.py](C:/Users/hy/ChapterGraph/feature_achievement/scripts/smoke_ask.py)
- optionally add a frontend manual checklist note if needed

### Changes

Cover this sequence:

1. blocked broad request
2. recommender returns narrower suggestions
3. user selects narrower term
4. resend with same user query and new term
5. response becomes either normal or at least less broad

Suggested manual validation example:

1. send:
   - `term=Spring`
   - `user_query=How does Spring implement data persistence?`
2. verify blocked state and suggestions:
   - `Spring Data`
   - `data persistence`
   - `JdbcTemplate`
   - `Spring Data JPA`
3. click `Spring Data`
4. resend
5. verify the response no longer uses the blocked broad-term state

### Validation commands

```powershell
python -m pytest -q tests/test_term_recommender.py tests/test_ask_api.py
python -m feature_achievement.scripts.smoke_ask
python -m pytest -q
```

### Done when

- the blocked-term narrowing flow works end to end

## Commit 07

### `feat(cache): add optional Redis storage for narrowing feedback`

Status: `pending`

### Scope

Files:
- add a small Redis helper module if needed
- router/frontend code only where feedback storage is explicitly wired

### Changes

Add Redis only as a support layer, not as recommendation source logic.

Store:

- normalized broad term
- normalized user query
- suggested terms
- optionally clicked term

Suggested key shape:

```text
ask:term_reco:{normalized_term}
```

Suggested field:

- normalized user query

Suggested value:

```json
{
  "suggested_terms": [...],
  "source": "rule_based"
}
```

If click feedback is added later, store that separately or extend the JSON value.

### Done when

- Redis can record recommendation history or feedback without owning the recommendation decision

## Execution Notes

### Order matters

Implement in this order:

1. extract recommender interface
2. wire recommender into backend blocked responses
3. expose structured recommendation metadata
4. make suggestion chips clickable
5. add narrowed-term interaction hint
6. validate retry flow end to end
7. only then add optional Redis support

Reason:

- the recommendation capability must exist before the UI can consume it
- Redis should support the feature, not define it

### Architecture principle

Keep the current implementation replaceable.

The first version may be:

- rule-based
- hardcoded
- corpus-aware

But the interface should be stable enough to later swap in:

- model-assisted recommendation
- graph-aware recommendation
- Redis-informed ranking
- agent-called tool execution

### Non-goals

Do not include these in the same series:

- semantic query rewriting
- typo correction
- automatic term substitution without user confirmation
- embedding-based recommendation ranking
- session memory
- full agent orchestration
