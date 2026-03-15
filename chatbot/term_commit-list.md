# Term Commit List

This document turns [term_optmize_plan.md](C:/Users/hy/ChapterGraph/chatbot/term_optmize_plan.md) into an implementation sequence.

Goal:

- keep `term` mode
- separate retrieval anchor from answer intent
- preserve current `ILIKE` seed path
- support richer user questions without breaking chapter mode
- make `term` mandatory in term mode instead of inferring it from `query`
- make `chapter_id` mandatory in chapter mode instead of inferring it from `query`

## Commit 01

### `feat(ask): require explicit term and chapter_id anchors in ask request`

Status: `completed`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/schemas/ask.py)
- [test_ask_request.py](C:/Users/hy/ChapterGraph/tests/test_ask_request.py)

### Changes

Add new request fields:

```python
query: str | None = None
term: str | None = None
user_query: str | None = None
```

Keep `query_type` as-is:

```python
query_type: Literal["term", "chapter"] = "term"
```

Validation behavior:

- `term` mode:
  - require `term`
  - if `user_query` missing, synthesize fallback from `term`
  - `query` is not a compatibility alias for `term`
- `chapter` mode:
  - require `chapter_id`
  - if `query` missing, synthesize fallback from `chapter_id`
  - do not infer `chapter_id` from `query`

Suggested normalization shape:

```python
@model_validator(mode="after")
def normalize(self):
    if self.query is not None:
        self.query = self.query.strip()
    if self.term is not None:
        self.term = self.term.strip()
    if self.user_query is not None:
        self.user_query = self.user_query.strip()
    if self.chapter_id is not None:
        self.chapter_id = self.chapter_id.strip()

    if self.query_type == "term":
        if not self.term:
            raise ValueError("term is required for term query_type")
        if not self.user_query:
            self.user_query = f'Explain the term "{self.term}" using the retrieved cluster.'
    else:
        if not self.chapter_id:
            raise ValueError("chapter_id is required for chapter query_type")
        if not self.query:
            self.query = f'Summarize the selected chapter "{self.chapter_id}" using the retrieved cluster.'
    return self
```

### Tests

Add/update cases for:

1. term mode with `term` only
2. term mode with `term + user_query`
3. term mode with missing `term` -> `422`
4. chapter mode with `chapter_id` only
5. chapter mode with `chapter_id + query`
6. chapter mode with missing `chapter_id` -> `422`

### Done when

- `AskRequest` accepts explicit-anchor term requests
- `AskRequest` accepts explicit-anchor chapter requests
- both modes can synthesize a default visible question

## Commit 02

### `feat(ask): use term for seed retrieval and evidence scoring`

Status: `completed`

### Scope

Files:
- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)
- [test_ask_cluster_builder.py](C:/Users/hy/ChapterGraph/tests/test_ask_cluster_builder.py)

### Changes

In `_pick_seed_ids()`:

- for `query_type="term"`, use `req.term`
- for `query_type="chapter"`, use `req.chapter_id`
- do not use `req.user_query` for `ILIKE`
- do not add anchor inference from `req.query`

Target change:

```python
term_ids = search_term_seed_ids_ilike(
    session=session,
    term=req.term or "",
    enrichment_version=req.enrichment_version,
    limit=req.seed_top_k,
)
```

In `_build_evidence()`:

- keep chapter mode evidence ordering logic unchanged
- for term mode lexical scoring, use `req.term` as query basis
- do not let generic user phrasing pollute overlap scoring

Target shape:

```python
query_basis = req.term if req.query_type == "term" else req.query
query_tokens = set(_normalize_text(query_basis or "").split())
```

### Tests

Add/update cases for:

1. `term="Actuator", user_query="Tell me about Actuator"` -> retrieval uses `Actuator`
2. `term="data persistence", user_query="为我讲讲它在 Spring 里的实现方式"` -> retrieval uses `data persistence`
3. term evidence ordering/scoring is still based on retrieval term
4. chapter mode remains anchored to `chapter_id`

### Done when

- natural-language `user_query` no longer breaks term seed lookup
- term evidence stays anchored to the term itself
- chapter mode stays anchored to `chapter_id`

## Commit 03

### `feat(llm): expose retrieval term in prompt building`

Status: `completed`

### Scope

Files:
- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)
- [qwen_client.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/qwen_client.py) if prompt-call signature needs update
- [test_qwen_prompts.py](C:/Users/hy/ChapterGraph/tests/test_qwen_prompts.py)

### Changes

Change prompt builder signature to distinguish:

- visible user question
- retrieval term

Target signature:

```python
def build_prompt(
    query: str,
    query_type: str,
    cluster: dict[str, object],
    retrieval_term: str | None = None,
) -> str:
```

Prompt behavior:

- term mode includes both:
  - `User question:`
  - `Retrieval term:`
- chapter mode includes only `User question:`

Example term prompt prefix:

```text
User question: Tell me about Actuator and focus on health endpoints.
Query type: term
Retrieval term: Actuator
```

### Tests

Add/update cases for:

1. term prompt includes retrieval term
2. term prompt still includes user question
3. chapter prompt does not include retrieval term
4. existing language-following instructions remain present

### Done when

- LLM sees both the retrieval anchor and the actual user intent
- no prompt regression for chapter mode

## Commit 04

### `feat(api): wire explicit anchors through /ask`

Status: `pending`

### Scope

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- any local answer-generation helper touched by the router
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

### Changes

Wire term mode so that:

- retrieval path uses `req.term`
- LLM prompt uses `req.user_query`
- fallback question is used when `user_query` is empty

Wire chapter mode so that:

- retrieval path uses `req.chapter_id`
- LLM prompt uses `req.query`
- fallback question is used when `query` is empty

Target behavior:

- term mode response can still expose a visible question in the response body if the response schema keeps `query`
- chapter mode response can still expose `query`
- but internally:
  - term `cluster` is built from `term`
  - term `answer` is generated from `user_query`
  - chapter `cluster` is built from `chapter_id`
  - chapter `answer` is generated from `query`

### Tests

Add/update cases for:

1. `term + user_query` request returns `200`
2. `term` only request returns `200`
3. missing `term` returns validation error
4. `chapter_id + query` request returns `200`
5. `chapter_id` only request returns `200`
6. missing `chapter_id` returns validation error

### Done when

- `/ask` accepts explicit-anchor requests end-to-end
- both modes strictly use the explicit contract

## Commit 05

### `feat(frontend): split term ask and require explicit chapter selection`

Status: `pending`

### Scope

Files:
- frontend entry file(s), likely [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- relevant HTML/CSS files used by the ask panel

### Changes

Update term tab UI:

- add required `Term` input
- add optional `Ask about this term` textarea

Keep chapter tab explicit:

- submit only when a chapter is selected
- send `chapter_id` explicitly
- allow chapter question to be empty

Payload shapes sent to `/ask`:

```js
{
  query_type: 'term',
  term: termValue,
  user_query: userQueryValue,
  run_id,
  enrichment_version,
  llm_enabled: true,
}
```

```js
{
  query_type: 'chapter',
  chapter_id: selectedChapterId,
  query: chapterQuestionValue,
  run_id,
  enrichment_version,
  llm_enabled: true,
}
```

UX rules:

- if `Term` empty, block submit client-side
- if no chapter selected, block chapter submit client-side
- optional question fields may be empty
- do not auto-concatenate fields

### Manual checks

1. term only submit works
2. term + detailed question works
3. chapter selected + empty question works
4. chapter selected + detailed question works
5. no selected chapter is blocked before submit

### Done when

- frontend no longer relies on backend guessing for either mode

## Commit 06

### `test(smoke): validate explicit-anchor flow and regression safety`

Status: `pending`

### Scope

Files:
- [smoke_ask.py](C:/Users/hy/ChapterGraph/feature_achievement/scripts/smoke_ask.py) if needed
- test files touched earlier
- optionally a dedicated smoke script if current one becomes clearer than modifying the existing one

### Changes

Update smoke or add one focused smoke path that covers:

1. term-only request
2. term + user_query request
3. chapter request with explicit query
4. chapter request with empty query

Recommended payloads:

```json
{
  "query_type": "term",
  "term": "Actuator",
  "user_query": "Tell me about Actuator and focus on metrics.",
  "run_id": 5,
  "enrichment_version": "v2_indexed_sections_bullets"
}
```

```json
{
  "query_type": "chapter",
  "chapter_id": "spring-start-here::ch8",
  "query": "为我讲解这章相关内容",
  "run_id": 5,
  "enrichment_version": "v2_indexed_sections_bullets"
}
```

```json
{
  "query_type": "chapter",
  "chapter_id": "spring-start-here::ch8",
  "query": "",
  "run_id": 5,
  "enrichment_version": "v2_indexed_sections_bullets"
}
```

### Validation commands

```powershell
python -m pytest -q tests/test_ask_request.py tests/test_ask_cluster_builder.py tests/test_qwen_prompts.py tests/test_ask_api.py
python -m feature_achievement.scripts.smoke_ask_cluster
python -m feature_achievement.scripts.smoke_ask
```

### Done when

- automated coverage exists for the explicit-anchor contract
- smoke confirms both ask modes are stable again for real DB-backed requests

## Execution Notes

### Order matters

Implement in this order:

1. schema
2. retrieval/evidence
3. prompt
4. router wiring
5. frontend
6. smoke/regression

Reason:

- schema first prevents ad hoc conditionals later
- retrieval must be correct before prompt quality matters
- frontend should only change after backend contract is stable

### Contract constraint

Backend and frontend should move to the explicit anchor contract together:

- `term` is required in term mode
- `user_query` is optional in term mode
- `chapter_id` is required in chapter mode
- `query` is optional in chapter mode

Do not add anchor inference from `query` in this series.

### Non-goals

Do not mix these into the same series:

- vector retrieval redesign
- term extraction from free-form questions
- multi-turn memory
- agent/tool orchestration
- chapter schema redesign
