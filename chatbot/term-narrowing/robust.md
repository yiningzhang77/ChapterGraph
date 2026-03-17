# Robustness Plan

## Goal

Add a robustness layer for term-mode `/ask` that distinguishes three cases instead of treating all non-empty retrieval as answerable:

1. normal answer
2. soft block with narrowing suggestions
3. controlled broad answer

The system should behave like this:

- if retrieval is broad or scattered and the user needs a precise answer, do not answer yet
- instead, return a structured narrowing response with hardcoded suggested terms
- if the user explicitly asks for a high-level concept answer, allow the answer
- but downgrade the prompt so the model gives only a broad concept explanation

This keeps the current Graph-RAG structure and adds a decision boundary on top of it.

## Three States

## 1. `normal`

Conditions:

- term is not broad
- evidence is not too scattered

Behavior:

- return `200`
- answer normally
- no retrieval warning or block state

## 2. `broad_blocked`

Conditions:

- retrieval is broad or scattered
- user request appears to need a precise answer

Behavior:

- do not generate an answer
- return a structured block response
- include hardcoded suggested terms
- tell the user to narrow the term first

This is the safe default for broad terms.

## 3. `broad_allowed`

Conditions:

- retrieval is broad or scattered
- user request is a definition-style or overview-style request

Behavior:

- return `200`
- allow answer generation
- downgrade the prompt so the model gives a broad concept-level answer only
- tell the user that a narrower term is needed for deeper analysis

This covers cases like:

- `What is Spring?`
- `Spring 是什么？`
- `Give me an overview of Spring`

## Why This Boundary Is Better

Current broad-term warning-only behavior is too weak for precise questions.

If the term is broad and the user asks a deep or comparative question, the system can stay grounded but still produce a vague blended answer.

The better rule is:

- if precision is required, broad retrieval should block
- if only a concept overview is required, broad retrieval can still answer

## Current Ask Flow

Current term-mode flow is:

1. `term` -> `ILIKE` seed lookup
2. seed chapters -> graph expansion
3. expanded chapters -> evidence sections and bullets
4. cluster + evidence -> LLM
5. answer returned to frontend

The best place to make the robustness decision is after cluster construction, because by then the system knows:

- seed count
- chapter spread
- book spread
- evidence distribution
- user query intent

No new database schema is required.

## Broad Retrieval Signals

## Signal A: term too broad

First-pass rule:

- `seed_count >= 5` -> broad retrieval signal

Reason:

- default `seed_top_k` is `5`
- once the term already matches `4` or more seeds, the answer is likely to spread

## Signal B: evidence too scattered

First-pass rules:

- `distinct evidence bullet chapter count >= 5`
- or `distinct evidence book count >= 3`

Reason:

- if top evidence bullets already span many chapters or many books, the final answer is unlikely to stay precise

## User Intent Split

Broad retrieval alone is not enough to decide whether to block.
You also need a simple classification of the user's requested answer style.

## 1. Definition or overview intent

Allow broad answer when the user is clearly asking for a high-level concept explanation.

Examples:

- `What is Spring?`
- `Spring 是什么？`
- `Give me an overview of Spring`
- `简单介绍一下 Spring`
- `Define Spring`

Simple first-pass keyword triggers:

English:

- `what is`
- `define`
- `overview`
- `introduce`

Chinese:

- `什么是`
- `是什么`
- `概览`
- `简单介绍`
- `简要说明`

## 2. Precise or analytical intent

Block broad answer when the user is asking for precision.

Examples:

- `Compare Spring and Spring Boot`
- `How does Spring implement data persistence?`
- `详细讲讲 Spring 的数据持久化实现`
- `Spring Security 和 Actuator 安全有什么区别？`

Simple first-pass keyword triggers:

English:

- `compare`
- `difference`
- `how`
- `why`
- `implement`
- `configuration`
- `best practice`
- `architecture`

Chinese:

- `区别`
- `对比`
- `怎么`
- `如何`
- `实现`
- `配置`
- `原理`
- `详细`
- `深入`
- `分析`

## Decision Matrix

## A. Retrieval is clean

- answer normally

## B. Retrieval is broad/scattered + intent is precise

- do not answer
- return narrowing guidance
- include hardcoded suggested terms

## C. Retrieval is broad/scattered + intent is definition-style

- answer allowed
- force high-level concept answer only
- do not perform deep analysis
- recommend a narrower follow-up term

## D. Retrieval is broad/scattered + no user query or unclear query

- default to block

Reason:

- if the user has not clearly asked for a concept overview, the safer default is to avoid a vague answer

## Examples

## Example 1: allowed broad concept answer

Input:

```json
{
  "query_type": "term",
  "term": "Spring",
  "user_query": "What is Spring?"
}
```

Expected behavior:

- broad retrieval detected
- intent classified as definition/overview
- answer allowed
- prompt downgraded to concept-level explanation only
- response includes warning metadata

## Example 2: blocked broad analytical answer

Input:

```json
{
  "query_type": "term",
  "term": "Spring",
  "user_query": "How does Spring implement data persistence?"
}
```

Expected behavior:

- broad retrieval detected
- intent classified as precise/analytical
- no answer generated
- response tells user to narrow the term
- hardcoded suggestions returned

## Example 3: blocked broad Chinese request

Input:

```json
{
  "query_type": "term",
  "term": "data",
  "user_query": "详细讲讲 data 在 Spring 里的实现"
}
```

Expected behavior:

- broad retrieval detected
- precise request detected
- block and suggest narrower terms

## Example 4: no seed

Input:

```json
{
  "query_type": "term",
  "term": "Actuatro",
  "user_query": "Tell me about Actuatro"
}
```

Expected behavior:

- no seed
- existing `422 No seed chapters found`

This remains a hard fail separate from broad/scattered retrieval.

## Hardcoded Suggested Terms

Do not generate suggestions dynamically yet.
Use a small static mapping.

Example:

```python
TERM_SUGGESTIONS = {
    "spring": ["Spring Boot", "Spring MVC", "Spring Data", "Spring Security"],
    "data": ["data persistence", "JdbcTemplate", "Spring Data JPA", "data source"],
    "security": ["Spring Security", "Actuator endpoint security", "authentication"],
}
```

Fallback suggestions if no mapping exists:

```python
DEFAULT_SUGGESTIONS = [
    "Actuator",
    "JdbcTemplate",
    "data persistence",
    "Spring Security",
]
```

## Backend Implementation

## 1. Replace simple warning-only logic with a retrieval quality decision

Best place:

- [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)

Add a helper like:

```python
def evaluate_term_retrieval_quality(
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
    user_query: str,
) -> dict[str, object] | None:
```

This helper should return one of:

- `None` for normal
- structured object for `broad_blocked`
- structured object for `broad_allowed`

### Suggested shape

```json
{
  "state": "broad_blocked",
  "term_too_broad": true,
  "evidence_too_scattered": true,
  "seed_count": 5,
  "seed_threshold": 5,
  "evidence_bullet_chapter_count": 7,
  "evidence_book_count": 3,
  "message": "This term is too broad for a precise answer. Please narrow it.",
  "suggested_terms": ["Spring Boot", "Spring Data", "Spring Security"]
}
```

or:

```json
{
  "state": "broad_allowed",
  "term_too_broad": true,
  "message": "This term is broad, so the answer is limited to a high-level concept overview.",
  "suggested_terms": ["Spring Boot", "Spring MVC", "Spring Data"]
}
```

## 2. Block precise broad answers before LLM

If state is `broad_blocked`:

- do not call `ask_qwen`
- return `200` with:
  - `answer_markdown = null`
  - `meta.retrieval_warnings = ...`
  - optional `meta.response_state = "needs_narrower_term"`

Do not use `4xx` here.

Reason:

- this is not an invalid request
- it is a valid request that the system refuses to answer precisely with current retrieval quality

## 3. Allow broad concept answers with a prompt downgrade

If state is `broad_allowed`:

- allow `ask_qwen`
- pass a prompt note such as:

```text
Warning: retrieval is broad. Give only a concise high-level concept explanation. Do not provide detailed analysis. Recommend narrower follow-up terms.
```

This ensures `Spring 是什么` gets a concept explanation rather than an over-claimed analytical answer.

## Frontend Implementation

## 1. Distinguish hard error, soft block, and normal answer

There are now three user-visible states:

1. hard fail
- `422 No seed chapters found`

2. soft block
- `200`
- `answer_markdown = null`
- `meta.retrieval_warnings.state = "broad_blocked"`

3. broad allowed answer
- `200`
- answer exists
- `meta.retrieval_warnings.state = "broad_allowed"`

The frontend must render these differently.

## 2. Soft block UI

Show:

- warning banner
- explanation message
- hardcoded suggested terms
- no assistant answer body

Suggested text:

- `This term is too broad for a precise answer. Please narrow it.`
- `Try: Spring Boot, Spring MVC, Spring Data, Spring Security`

## 3. Broad allowed UI

Show:

- answer body
- warning banner above it
- suggested follow-up terms below the warning

Suggested text:

- `This term is broad, so the answer below is a high-level overview only.`

## API Contract Shape

Recommended response for blocked broad request:

```json
{
  "query": "How does Spring implement data persistence?",
  "query_type": "term",
  "answer_markdown": null,
  "meta": {
    "schema_version": "cluster.v1",
    "response_state": "needs_narrower_term",
    "retrieval_warnings": {
      "state": "broad_blocked",
      "term_too_broad": true,
      "seed_count": 5,
      "message": "This term is too broad for a precise answer. Please narrow it.",
      "suggested_terms": ["Spring Data", "JdbcTemplate", "data persistence"]
    }
  }
}
```

Recommended response for allowed broad overview:

```json
{
  "query": "What is Spring?",
  "query_type": "term",
  "answer_markdown": "...",
  "meta": {
    "schema_version": "cluster.v1",
    "response_state": "broad_overview",
    "retrieval_warnings": {
      "state": "broad_allowed",
      "term_too_broad": true,
      "message": "This term is broad, so the answer is limited to a high-level overview.",
      "suggested_terms": ["Spring Boot", "Spring MVC", "Spring Data"]
    }
  }
}
```

## Tests To Add

## Backend tests

Cases:

1. broad retrieval + precise intent -> blocked response, no answer
2. broad retrieval + definition intent -> allowed answer
3. broad retrieval + empty query -> blocked response
4. clean retrieval -> normal response
5. no seed -> existing hard fail remains

## Frontend checks

Manual checks:

1. `term=Spring`, `user_query=What is Spring?` -> answer plus broad-overview warning
2. `term=Spring`, `user_query=How does Spring implement data persistence?` -> no answer, narrowing suggestions shown
3. `term=data`, `user_query=详细讲讲 data 在 Spring 里的实现` -> blocked with suggestions
4. `term=Actuator`, `user_query=Tell me about Actuator` -> normal answer, no block
5. `term=Actuatro` -> hard error

## Recommended Implementation Order

1. backend retrieval-quality evaluator
2. hardcoded suggestion table
3. blocked/allowed response states in router
4. optional prompt downgrade for broad allowed
5. frontend UI for soft block and broad allowed banner
6. tests and manual validation

## Non-goals

Do not include these in the same change:

- typo correction
- semantic suggestion generation
- embedding-based ambiguity detection
- auto-rewriting the user term
- agent-style clarification loops

## Bottom Line

The right boundary is:

- no seed -> hard fail
- broad retrieval + precise question -> block and ask user to narrow the term
- broad retrieval + concept question -> allow, but only answer at concept level

In one sentence:

- if precision is needed, broad retrieval should not answer
- if the user only wants a concept definition, broad retrieval may answer, but only as a broad overview
