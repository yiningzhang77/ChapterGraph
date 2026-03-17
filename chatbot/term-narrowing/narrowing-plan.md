# Narrowing Plan

## Goal

When a broad term request is blocked, the system should do more than say:

- `Please narrow the term`

It should recommend the next concrete term the user should ask about.

Example:

Input:

```json
{
  "query_type": "term",
  "term": "Spring",
  "user_query": "How does Spring implement data persistence?"
}
```

Desired outcome:

- block the current request
- explain that `Spring` is too broad for a precise answer
- recommend more specific follow-up terms such as:
  - `Spring Data`
  - `data persistence`
  - `JdbcTemplate`
  - `Spring Data JPA`

## Core Principle

The first problem is:

- how to recommend narrower terms

It is not:

- where to store the recommendation result

Therefore the implementation order should be:

1. rule-based narrowing recommender
2. frontend suggestion-click flow
3. optional Redis feedback/history cache

Do not start with Redis as the main logic.

## Phase 1: Rule-Based Narrowing Recommender

## Objective

Given:

- a blocked broad term
- a precise user query

Return:

- a small ranked list of narrower follow-up terms
- an optional reason

## Why Rule-Based First

At the current project stage:

- retrieval is real
- broad-term blocking is real
- failure cases are visible
- corpus is still small and known

That makes a rule-based first version the fastest way to discover:

- what patterns matter
- what the tool contract should look like later

## Proposed Module

Add a dedicated module:

- `feature_achievement/ask/term_recommender.py`

Do not keep growing recommendation logic inside:

- `retrieval_quality.py`

Reason:

- retrieval quality and term recommendation are related, but they are not the same responsibility

## Proposed Interface

```python
def recommend_narrower_terms(
    *,
    broad_term: str,
    user_query: str,
) -> dict[str, object]:
    ...
```

Suggested output:

```json
{
  "reason": "broad_term_precise_query",
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

## First-Pass Rule Shape

Use a two-stage rule set.

### Stage A: broad term family

Example:

```python
BROAD_TERM_RULES = {
    "spring": [
        ...
    ],
    "data": [
        ...
    ],
    "security": [
        ...
    ],
}
```

### Stage B: user-query topic match

For each broad term, define query-topic buckets.

Example:

```python
BROAD_TERM_RULES = {
    "spring": [
        {
            "match_any": ["data", "persistence", "jdbc", "jpa", "repository"],
            "suggested_terms": [
                "Spring Data",
                "data persistence",
                "JdbcTemplate",
                "Spring Data JPA",
            ],
            "reason": "spring_persistence",
        },
        {
            "match_any": ["web", "mvc", "controller", "request"],
            "suggested_terms": [
                "Spring MVC",
                "controller",
                "request mapping",
            ],
            "reason": "spring_web",
        },
        {
            "match_any": ["security", "auth", "authentication", "authorization"],
            "suggested_terms": [
                "Spring Security",
                "authentication",
                "authorization",
            ],
            "reason": "spring_security",
        },
    ]
}
```

## Matching Strategy

Keep the first version simple:

1. normalize broad term
2. normalize user query
3. find matching broad-term bucket
4. check `match_any` keywords against the query
5. return the first matching recommendation set
6. if nothing matches, fall back to existing generic suggestions

This should remain lexical for now.
Do not bring embeddings or semantic routing into this step yet.

## Backend Wiring

Current blocked response already returns:

- `meta.response_state = "needs_narrower_term"`
- `meta.retrieval_warnings.suggested_terms`

Update that flow so `suggested_terms` comes from the new recommender module instead of a single static map.

Recommended responsibility split:

- `retrieval_quality.py`
  - decides whether the request is normal / broad-blocked / broad-allowed

- `term_recommender.py`
  - decides which narrower terms to suggest

## Important Retrieval Reality

A narrower term for a human reader is not automatically a stable retrieval anchor for the current system.

Example from the current corpus:

- `Spring Data` is semantically narrower than `Spring`
- but it can still produce a broad or scattered retrieval result
- meanwhile `data persistence` or `JdbcTemplate` can be more stable anchors in the current DB

This means the recommender must eventually care about two things:

1. semantic narrowing quality
2. retrieval focus quality in the current ChapterGraph pipeline

So the first recommender can stay rule-based, but later recommendation ranking should become retrieval-aware.

## Follow-Up Capability After Phase 1

Before Redis, the most useful next capability is a light candidate-anchor evaluator.

Goal:

- given a suggested narrower term
- quickly estimate whether it is likely to clear the blocked broad-term state

Possible future interface:

```python
def evaluate_candidate_anchor(
    *,
    term: str,
    user_query: str,
    run_id: int,
    enrichment_version: str,
) -> dict[str, object]:
    ...
```

Possible output:

```json
{
  "focus_state": "focused",
  "expected_response_state": "normal",
  "seed_count": 3
}
```

This should be treated as a later step.
It is useful because it can rerank recommender outputs by actual retrieval behavior instead of semantic guesswork alone.

## Expected Behavior

### Example A

Input:

- `term=Spring`
- `user_query=How does Spring implement data persistence?`

Output suggestions:

- `Spring Data`
- `data persistence`
- `JdbcTemplate`
- `Spring Data JPA`

## Implementation Principle

At this stage, the priority is not to make narrowing recommendation maximally intelligent.
The priority is to make the interface and flow explicit.

That means:

- keep the recommendation module behind a clear callable interface
- wire the blocked-term flow end to end
- make the recommendation step replaceable later

This is the right order because later the same interface can be upgraded from:

- rule-based logic
- hardcoded heuristics

to:

- model-assisted recommendation
- graph-aware recommendation
- Redis-informed ranking
- agent-called tools

without forcing a redesign of `/ask`.

So the current target is:

- abstract the capability
- stabilize the flow
- defer intelligence upgrades

### Example B

Input:

- `term=Spring`
- `user_query=How do controllers work in Spring?`

Output suggestions:

- `Spring MVC`
- `controller`
- `request mapping`

### Example C

Input:

- `term=Spring`
- `user_query=How is authentication handled in Spring?`

Output suggestions:

- `Spring Security`
- `authentication`
- `authorization`

### Example D

Input:

- `term=data`
- `user_query=How is data access implemented?`

Output suggestions:

- `data persistence`
- `JdbcTemplate`
- `Spring Data JPA`
- `data source`

## Tests For Phase 1

Add focused tests for:

1. `Spring` + persistence query -> persistence-related suggestions
2. `Spring` + web query -> web-related suggestions
3. `Spring` + security query -> security-related suggestions
4. unmatched query -> fallback suggestions
5. unmatched broad term -> fallback suggestions

## Phase 2: Frontend Suggestion Click Flow

## Objective

When the backend returns a blocked broad-term state with `suggested_terms`, the frontend should not only display them.
It should let the user continue with one click.

## Desired UX

Blocked response card shows:

- warning message
- list of suggested narrower terms as clickable chips/buttons

When the user clicks one:

1. fill the `Term` input with the clicked suggestion
2. keep the existing `user_query`
3. optionally focus the send button or auto-submit

Recommended first version:

- fill the term input
- do not auto-submit

Reason:

- the user should still have a chance to inspect or edit the revised term

## Frontend Behavior Example

Before click:

- `term = Spring`
- `user_query = How does Spring implement data persistence?`

Blocked state suggests:

- `Spring Data`
- `data persistence`
- `JdbcTemplate`
- `Spring Data JPA`

User clicks `Spring Data`

After click:

- `term = Spring Data`
- `user_query = How does Spring implement data persistence?`

User then sends again.

## Frontend Implementation Points

Likely file:

- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)

Add:

- click handler for suggested-term chips
- state update for term input
- optional small hint that the query has been narrowed

## Tests / Manual Validation For Phase 2

Manual flow:

1. send blocked broad query
2. verify chips appear
3. click one chip
4. verify term input updates
5. resend
6. verify request is no longer blocked if retrieval becomes focused enough

## Phase 3: Optional Redis Feedback Cache

## Objective

Once the recommender works, Redis can help store:

- recommendation history
- click feedback
- repeated broad-query patterns

This is optional support infrastructure.
It should not define the recommendation logic in the first version.

Redis is still not the next priority after Phase 1.
The better next step is candidate-anchor evaluation, because the current problem is recommendation quality, not recommendation storage.

## What Redis Should Store

Store recommendation behavior, not just assistant answers.

Better fit:

- broad term
- normalized user query
- recommended narrower terms
- clicked term if the user picked one

Less useful as a first step:

- `user_query -> assistant_answer`

That is answer caching, not narrowing intelligence.

## Recommended Redis Key Shape

Keep term mode separate from chapter mode.

Example:

```text
ask:term_reco:{normalized_term}
```

Hash field:

- normalized user query

Hash value:

- JSON array or JSON object of suggested terms and metadata

Example:

```text
key   = ask:term_reco:spring
field = how does spring implement data persistence
value = {
  "suggested_terms": [
    "Spring Data",
    "data persistence",
    "JdbcTemplate",
    "Spring Data JPA"
  ],
  "source": "rule_based"
}
```

## Better Use Of Redis Later

After clicks are available in the UI, Redis can additionally store:

- which suggested term the user clicked
- click count
- success/failure after re-asking

That would allow later improvements such as:

- reorder suggestions by actual user choice
- identify popular narrowing paths
- detect useless suggestions

## Important Boundary

Redis should support these questions:

- what did we recommend before?
- what did users actually click?
- which narrowing paths work best?

Redis should not answer the first version of:

- what should we recommend?

That should stay rule-based first.

## Suggested Implementation Order

## Commit 01

- add `term_recommender.py`
- add rule-based suggestion buckets
- add unit tests for recommendation outputs

## Commit 02

- wire recommender into blocked broad-term backend responses
- keep fallback suggestions for unmatched cases
- update API tests

## Commit 03

- make suggested-term chips clickable in frontend
- fill the term input on click
- keep user query unchanged

## Commit 04

- add optional UI hint after a suggestion click
- validate resend flow manually

## Commit 05

- add optional Redis cache for recommendation history
- do not change recommendation source logic yet

## Non-Goals

Do not include these in the first narrowing series:

- embeddings for term recommendation
- typo correction
- semantic query rewriting
- automatic term substitution without user confirmation
- full conversational memory
- agent orchestration

## Bottom Line

The right next step is:

- first make blocked broad-term responses smarter with rule-based narrower-term recommendations
- then let the user click those suggestions in the frontend
- after that, improve recommendation quality with retrieval-aware candidate evaluation
- only then add Redis as a feedback/cache layer

That sequence solves the actual problem first and keeps the architecture honest.
