# Robust Commit List

This document turns [robust.md](C:/Users/hy/ChapterGraph/chatbot/term-narrowing/robust.md) into an implementation sequence.

Goal:

- classify broad term retrieval as either blocked or allowed
- block broad retrieval when the user needs precision
- allow broad retrieval only for concept/overview questions
- return hardcoded suggested terms when the user should narrow the term
- show these states clearly in the frontend

This series must not redesign retrieval.
It only adds a decision boundary on top of the current `/ask` pipeline.

## Commit 01

### `feat(ask): add term retrieval quality evaluator`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- optionally a small helper module if router logic becomes too crowded

### Changes

Add a helper that evaluates term-mode retrieval quality using:

- seed count
- evidence chapter spread
- evidence book spread
- user query intent

Target helper shape:

```python
def evaluate_term_retrieval_quality(
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
    user_query: str,
) -> dict[str, object] | None:
```

Initial thresholds:

- `seed_count >= 5` -> broad signal
- `distinct evidence bullet chapter count >= 5` -> scattered signal
- `distinct evidence book count >= 3` -> scattered signal

Initial outputs:

- `None` for normal
- `state="broad_blocked"`
- `state="broad_allowed"`

### Done when

- term requests can be classified into normal / blocked / allowed states without changing retrieval itself

## Commit 02

### `feat(ask): add hardcoded term suggestions for blocked broad terms`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py) or a small helper module

### Changes

Add a small static suggestion map.

Example:

```python
TERM_SUGGESTIONS = {
    "spring": ["Spring Boot", "Spring MVC", "Spring Data", "Spring Security"],
    "data": ["data persistence", "JdbcTemplate", "Spring Data JPA", "data source"],
    "security": ["Spring Security", "Actuator endpoint security", "authentication"],
}
```

Fallback:

```python
DEFAULT_SUGGESTIONS = [
    "Actuator",
    "JdbcTemplate",
    "data persistence",
    "Spring Security",
]
```

The evaluator should include `suggested_terms` in blocked and allowed broad states.

### Done when

- broad responses include concrete next-step term suggestions

## Commit 03

### `feat(api): block precise broad-term answers and expose response state`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

If retrieval quality state is `broad_blocked`:

- do not call `ask_qwen`
- return `200`
- `answer_markdown = null`
- set `meta.response_state = "needs_narrower_term"`
- set `meta.retrieval_warnings = ...`

Do not use `4xx` for this state.

### Tests

Add/update API tests for:

1. broad retrieval + precise intent -> no answer, blocked state returned
2. broad retrieval + empty user query -> blocked state returned
3. chapter mode does not use this logic

### Done when

- the backend refuses broad precise answers without pretending the request was invalid

## Commit 04

### `feat(llm): allow broad concept answers with prompt downgrade`

Status: `completed`

### Scope

Files:
- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)
- [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py) if needed
- [test_qwen_prompts.py](C:/Users/hy/ChapterGraph/tests/test_qwen_prompts.py)
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

If retrieval quality state is `broad_allowed`:

- still answer
- add a prompt note like:

```text
Warning: retrieval is broad. Give only a concise high-level concept explanation. Do not provide detailed analysis. Recommend narrower follow-up terms.
```

Return metadata:

- `meta.response_state = "broad_overview"`
- `meta.retrieval_warnings.state = "broad_allowed"`

### Tests

Add/update tests for:

1. broad retrieval + `What is X` -> answer allowed
2. prompt includes broad-overview downgrade note
3. answer path still works for clean retrieval

### Done when

- broad concept requests are answered honestly at the right granularity

## Commit 05

### `feat(frontend): render blocked broad-term state and suggested terms`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- [index.html](C:/Users/hy/ChapterGraph/frontend/index.html)

### Changes

Add a dedicated UI state for:

- `meta.response_state = "needs_narrower_term"`

Display:

- warning banner
- no assistant answer body
- suggested terms row/list

Suggested text:

- `This term is too broad for a precise answer. Please narrow it.`
- `Try: Spring Boot, Spring MVC, Spring Data, Spring Security`

### Done when

- the frontend clearly distinguishes a soft block from a hard error and from a normal answer

## Commit 06

### `feat(frontend): render broad overview warning above allowed broad answers`

Status: `completed`

### Scope

Files:
- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- [index.html](C:/Users/hy/ChapterGraph/frontend/index.html)

### Changes

Add a dedicated UI state for:

- `meta.response_state = "broad_overview"`

Display:

- warning banner above the answer
- suggested terms below the banner
- keep answer body visible

Suggested text:

- `This term is broad, so the answer below is a high-level overview only.`

### Done when

- the frontend makes it clear that the answer is intentionally broad and not a precise analysis

## Commit 07

### `test(smoke): validate normal, blocked, and broad-overview paths`

Status: `completed`

### Scope

Files:
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)
- [test_qwen_prompts.py](C:/Users/hy/ChapterGraph/tests/test_qwen_prompts.py)
- optionally [smoke_ask.py](C:/Users/hy/ChapterGraph/feature_achievement/scripts/smoke_ask.py) if warning-state smoke becomes useful

### Changes

Cover these cases:

1. clean term -> normal answer
2. broad term + precise question -> blocked
3. broad term + definition question -> broad overview answer
4. misspelled term -> existing hard error

Suggested manual validation inputs:

- `term=Actuator`, `user_query=Tell me about Actuator`
- `term=Spring`, `user_query=What is Spring?`
- `term=Spring`, `user_query=How does Spring implement data persistence?`
- `term=data`, `user_query=详细讲讲 data 在 Spring 里的实现`
- `term=Actuatro`, `user_query=Tell me about Actuatro`

### Validation commands

```powershell
python -m pytest -q tests/test_ask_api.py tests/test_qwen_prompts.py
python -m pytest -q
```

### Done when

- all three response states are covered and stable

## Execution Notes

### Order matters

Implement in this order:

1. backend retrieval-quality evaluator
2. hardcoded suggestion map
3. blocked broad-term response path
4. broad-overview prompt downgrade
5. frontend blocked state
6. frontend broad-overview state
7. tests and smoke

Reason:

- the backend state machine must be stable before the UI can render it cleanly

### Contract constraint

Keep these boundaries:

- `no seed` -> hard fail (`422`)
- `broad retrieval + precise question` -> soft block (`200`, no answer)
- `broad retrieval + concept question` -> controlled broad answer (`200`, downgraded prompt)

### Non-goals

Do not include these in the same series:

- typo correction
- semantic suggestion generation
- embedding-based ambiguity detection
- auto-rewriting the user term
- agent-style clarification loops
