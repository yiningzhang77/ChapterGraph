# Term Optimize Plan

## Goal

Keep `term` mode, but split its two responsibilities:

- `term`: retrieval seed input for `ILIKE` or later vector search.
- `user_query`: the actual user request sent to the LLM.

At the same time, make chapter mode structurally consistent:

- `chapter_id`: retrieval/selection anchor.
- `query`: optional visible user request.

This removes the current mismatch where `/ask` uses a single `query` for both retrieval and answer generation in term mode, and where chapter mode still relies on `query` as both locator fallback and question.

Current failure mode:

- `Actuator` works.
- `data persistence` works.
- `tell me about Actuator` fails at seed retrieval.
- `为我讲讲有关 data persistence` fails at seed retrieval.

Root cause:

- [`AskRequest`](C:/Users/hy/ChapterGraph/feature_achievement/api/schemas/ask.py) has only `query`.
- [`_pick_seed_ids()`](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py) sends `req.query` directly into `search_term_seed_ids_ilike()`.
- [`build_prompt()`](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py) also uses the same `query` as the user question.
- chapter mode still treats `query` as required even though the real anchor is `chapter_id`.

## Target Contract

### Term mode

Request shape:

```json
{
  "query_type": "term",
  "term": "Actuator",
  "user_query": "Tell me about Actuator and focus on health endpoints and metrics.",
  "run_id": 5,
  "enrichment_version": "v2_indexed_sections_bullets",
  "llm_enabled": true
}
```

Rules:

- `term` is required for `query_type="term"`.
- `user_query` is optional.
- If `user_query` is omitted, backend builds a default question from `term`.

### Chapter mode

Request shape:

```json
{
  "query_type": "chapter",
  "chapter_id": "spring-start-here::ch8",
  "query": "为我讲解这章相关内容",
  "run_id": 5
}
```

Rules:

- `chapter_id` is required for `query_type="chapter"`.
- `query` is optional.
- If `query` is omitted, backend builds a default chapter question from `chapter_id`.

This keeps chapter mode aligned with term mode:

- one explicit retrieval anchor
- one optional visible user question

## Desired Backend Behavior

### Retrieval side

For `query_type="term"`:

- use `term` for seed retrieval
- use `term` for section/bullet evidence scoring
- do not use `user_query` for `ILIKE`

For `query_type="chapter"`:

- use `chapter_id` for seed retrieval
- use `query` only for answer/evidence focus if it exists
- if `query` is omitted, use a deterministic chapter-summary fallback

### Answer side

For `query_type="term"`:

- use `user_query` as the visible user question in prompt building
- if `user_query` is missing, synthesize a fallback question

Suggested fallback:

```text
Explain the term "{term}" using the retrieved cluster.
```

For `query_type="chapter"`:

- use `query` as the visible user question in prompt building
- if `query` is missing, synthesize a fallback question

Suggested fallback:

```text
Summarize the selected chapter "{chapter_id}" using the retrieved cluster.
```

## Implementation Steps

## 1. Extend `AskRequest`

File:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/schemas/ask.py)

Add fields:

```python
class AskRequest(BaseModel):
    query: str | None = None
    term: str | None = None
    user_query: str | None = None
    query_type: Literal["term", "chapter"] = "term"
    ...
```

Validation rules:

- term mode:
  - `term` required
  - `user_query` optional
- chapter mode:
  - `chapter_id` required
  - `query` optional

Normalization strategy:

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

Why keep `query` at all:

- it remains the chapter-mode visible question field
- it avoids renaming the response schema immediately
- it keeps prompt-building call sites simpler in the short term

## 2. Separate retrieval query from answer query

File:
- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)

Current term retrieval:

```python
term_ids = search_term_seed_ids_ilike(
    session=session,
    term=req.query,
    enrichment_version=req.enrichment_version,
    limit=req.seed_top_k,
)
```

Change to:

```python
term_ids = search_term_seed_ids_ilike(
    session=session,
    term=req.term or "",
    enrichment_version=req.enrichment_version,
    limit=req.seed_top_k,
)
```

Then in `_build_evidence()` use the retrieval anchor, not the visible user question:

```python
query_basis = req.term if req.query_type == "term" else req.query
query_tokens = set(_normalize_text(query_basis or "").split())
```

Reason:

- `user_query="Tell me about Actuator and compare it with Admin server"`
- retrieval/evidence should still be centered on `Actuator`
- otherwise lexical overlap gets polluted by generic words

For chapter mode this remains acceptable because `req.query` will always be present after normalization, either from the user or from the fallback.

## 3. Make prompt building explicit

File:
- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)

Current shape:

```python
def build_prompt(query: str, query_type: str, cluster: dict[str, object]) -> str:
```

Change to:

```python
def build_prompt(
    query: str,
    query_type: str,
    cluster: dict[str, object],
    retrieval_term: str | None = None,
) -> str:
```

Prompt body for term mode should distinguish the two roles:

```python
return (
    f"User question: {query}\n"
    f"Query type: {query_type}\n"
    + (f"Retrieval term: {retrieval_term}\n\n" if retrieval_term else "\n")
    + _query_type_tasks(query_type)
    + f"Cluster JSON:\n{json.dumps(cluster, ensure_ascii=False)}"
)
```

This lets the model know:

- what the user actually wants
- what retrieval was anchored on

## 4. Wire router/service call sites

Files:
- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- any helper calling `build_prompt()` or `generate_answer()`

Term mode should send:

- answer question: `req.user_query`
- retrieval term: `req.term`

Chapter mode should send:

- answer question: `req.query`
- retrieval term: `None`

Example:

```python
answer = generate_answer(
    query=req.user_query if req.query_type == "term" else req.query,
    query_type=req.query_type,
    cluster=cluster,
    model=req.llm_model,
    timeout_ms=req.llm_timeout_ms,
    retrieval_term=req.term if req.query_type == "term" else None,
)
```

## 5. Frontend: term tab becomes dual-input

Current problem:

- one input box implies natural-language search
- backend term mode actually expects a retrieval phrase

Recommended UI change:

- `Term` input
- `Ask about this term` textarea

Example payload:

```js
{
  query_type: 'term',
  term: termInputValue,
  user_query: questionInputValue || '',
  run_id,
  enrichment_version,
  llm_enabled: true,
}
```

UI behavior:

- `Term` is required
- `Ask about this term` is optional
- if optional field is empty, backend fallback question is used

Example UX copy:

- term placeholder: `Actuator / JdbcTemplate / data persistence`
- user query placeholder: `Ask a specific question about this term...`

## 6. Compatibility policy

Do not hard-break chapter callers semantically, but do tighten the API contract:

- term mode requires `term`
- chapter mode requires `chapter_id`
- term mode no longer infers `term` from `query`
- chapter mode no longer infers `chapter_id` from `query`

This makes the API explicit and removes backend guessing.

## 7. Tests to add or update

### Schema tests

File:
- [test_ask_request.py](C:/Users/hy/ChapterGraph/tests/test_ask_request.py)

Add cases:

1. term mode accepts `term` without `user_query`
2. term mode synthesizes fallback `user_query`
3. term mode rejects missing `term`
4. chapter mode accepts `chapter_id` without `query`
5. chapter mode synthesizes fallback `query`
6. chapter mode rejects missing `chapter_id`

### Cluster builder tests

File:
- [test_ask_cluster_builder.py](C:/Users/hy/ChapterGraph/tests/test_ask_cluster_builder.py)

Add cases:

1. term retrieval uses `req.term`, not `req.user_query`
2. term evidence scoring uses `req.term`
3. chapter mode remains anchored to `chapter_id`
4. chapter mode still builds ordered evidence with fallback query present

Example:

```python
req = AskRequest.model_validate(
    {
        "query_type": "term",
        "term": "Actuator",
        "user_query": "Tell me about Actuator and compare it with JMX",
        "run_id": 5,
    }
)
```

Assert that `_pick_seed_ids()` sends `Actuator` into search.

### Prompt tests

File:
- [test_qwen_prompts.py](C:/Users/hy/ChapterGraph/tests/test_qwen_prompts.py)

Add cases:

1. term prompt includes `User question:`
2. term prompt includes `Retrieval term:`
3. chapter prompt does not include `Retrieval term:`
4. chapter prompt still receives a visible question when the user omitted one

### API tests

File:
- [test_ask_api.py](C:/Users/hy/ChapterGraph/tests/test_ask_api.py)

Add cases:

1. term request with `term + user_query` returns 200
2. term request with `term` only returns 200
3. term request missing `term` returns 422
4. chapter request with `chapter_id + query` returns 200
5. chapter request with `chapter_id` only returns 200
6. chapter request missing `chapter_id` returns 422

## 8. Smoke validation

After implementation, run:

```powershell
python -m pytest -q tests/test_ask_request.py tests/test_ask_cluster_builder.py tests/test_qwen_prompts.py tests/test_ask_api.py
python -m feature_achievement.scripts.smoke_ask_cluster
```

Then manual UI validation:

1. term=`Actuator`, user_query=`Tell me about Actuator`
2. term=`data persistence`, user_query=`为我讲讲它在 Spring 里的常见实现方式，用中文回答`
3. term=`JdbcTemplate`, user_query empty
4. chapter_id=`spring-start-here::ch8`, query explicit
5. chapter_id=`spring-start-here::ch8`, query empty

## 9. Non-goals for this change

Do not include these in the same commit set:

- vector retrieval redesign
- automatic term extraction from natural-language questions
- memory, multi-turn state, or agent logic

Those can come later. This change only separates retrieval anchor from answer intent and removes request-shape ambiguity.

## Recommended Commit Split

1. `feat(ask): require explicit term and chapter_id anchors in ask request`
2. `feat(ask): use term for seed retrieval and evidence scoring`
3. `feat(llm): expose retrieval term in prompt building`
4. `feat(frontend): split term ask into term plus user query inputs`
5. `test(ask): cover explicit anchor contract and dual-input flow`
