# Candidate Anchor Plan

## Goal

After broad-term blocking and rule-based narrowing recommendation are working, the next useful capability is:

- evaluate whether a suggested narrower term is actually a stable retrieval anchor in the current system

This is needed because a term can be:

- semantically narrower for a human
- but still broad or scattered for the current retrieval pipeline

Example:

- `Spring Data` is narrower than `Spring`
- but in the current corpus it can still remain broad
- while `data persistence` or `JdbcTemplate` may produce a more focused cluster

So the next step is not Redis.
The next step is a cheap retrieval-aware evaluator.

## Problem Statement

Current recommendation flow is:

1. broad term is blocked
2. recommender suggests narrower terms
3. frontend lets the user retry with one of them

This is already useful.
But it still assumes all suggested terms are similarly good retry anchors.

That assumption is false.

The missing capability is:

- estimate which suggested term is most likely to clear the blocked state

## Desired Outcome

Given:

- original broad term
- user query
- a list of suggested narrower terms

Return:

- a ranked list of suggested terms
- optionally with focus metadata per candidate

Example:

Input suggestions:

```json
[
  "Spring Data",
  "data persistence",
  "JdbcTemplate",
  "Spring Data JPA"
]
```

Desired ranked output:

```json
[
  {
    "term": "data persistence",
    "focus_state": "focused",
    "expected_response_state": "normal",
    "seed_count": 3
  },
  {
    "term": "JdbcTemplate",
    "focus_state": "focused",
    "expected_response_state": "normal",
    "seed_count": 2
  },
  {
    "term": "Spring Data JPA",
    "focus_state": "acceptable",
    "expected_response_state": "normal",
    "seed_count": 4
  },
  {
    "term": "Spring Data",
    "focus_state": "broad",
    "expected_response_state": "needs_narrower_term",
    "seed_count": 5
  }
]
```

## Position In The Flow

The evaluator belongs between:

- `term_recommender.py`
- frontend suggestion rendering

Proposed flow:

1. broad term gets blocked
2. recommender generates candidate narrower terms
3. candidate-anchor evaluator probes those candidates
4. backend returns reranked suggestions
5. frontend renders the better-ordered list

This keeps recommendation generation and recommendation ranking separate.

## Responsibility Split

## `term_recommender.py`

Owns:

- semantic / heuristic candidate generation
- corpus-specific rule buckets

Does not own:

- actual retrieval-focus validation

## `retrieval_quality.py`

Owns:

- broad vs blocked vs allowed state classification

Does not own:

- candidate ranking

## candidate-anchor evaluator

Owns:

- cheap probe of candidate terms against current retrieval behavior
- ranking/filtering of suggested terms

Does not own:

- initial suggestion generation
- LLM answer generation

## Proposed Module

Add a dedicated module such as:

- `feature_achievement/ask/candidate_anchor.py`

## Proposed Interface

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

## Proposed Output Shape

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

Possible `focus_state` values:

- `focused`
- `acceptable`
- `broad`
- `no_seed`

Possible `expected_response_state` values:

- `normal`
- `broad_overview`
- `needs_narrower_term`
- `no_seed`

## Cheap Probe Strategy

Do not call the LLM.
Do not run a full answer path.

Just reuse the current retrieval stack cheaply:

1. build a temporary term request
2. run cluster construction
3. inspect:
   - seed count
   - evidence chapter spread
   - evidence book spread
4. run the same retrieval-quality logic
5. summarize the result

In other words:

- probe candidate terms using the exact system that will later answer them
- but stop before prompt / LLM

## Implementation Detail

The probe should reuse current logic as much as possible:

- `build_cluster(...)`
- `evaluate_term_retrieval_quality(...)`

That is better than inventing a second approximation layer.

The evaluator should be a thin orchestrator over existing retrieval logic.

## Ranking Heuristic

First version ranking can be simple:

1. candidates with `expected_response_state = normal`
2. then lower `seed_count`
3. then lower `evidence_book_count`
4. then lower `evidence_chapter_count`
5. blocked candidates last
6. `no_seed` candidates last of all

This is enough for a first retrieval-aware rerank.

## Recommended Backend Behavior

When a broad term is blocked:

1. generate candidate terms with recommender
2. probe and rank them
3. return:
   - `suggested_terms` in reranked order
   - optional `suggested_term_diagnostics`

Example:

```json
{
  "suggested_terms": [
    "data persistence",
    "JdbcTemplate",
    "Spring Data JPA",
    "Spring Data"
  ],
  "suggested_term_diagnostics": [
    {
      "term": "data persistence",
      "expected_response_state": "normal"
    },
    {
      "term": "Spring Data",
      "expected_response_state": "needs_narrower_term"
    }
  ]
}
```

The frontend can initially ignore diagnostics and just use the improved order.

## Important Constraint

Do not turn this into a recursive retrieval explosion.

Guardrails:

- evaluate only the top few suggested terms, for example `<= 4`
- no graph expansion beyond current `/ask` defaults
- no LLM call

This must stay cheap.

## Manual Validation Example

Input:

- `term=Spring`
- `user_query=How does Spring implement data persistence?`

Expected outcome:

- blocked broad request
- recommender generates:
  - `Spring Data`
  - `data persistence`
  - `JdbcTemplate`
  - `Spring Data JPA`
- candidate-anchor evaluator reranks them so that more focused anchors move earlier

Expected real behavior in the current corpus:

- `data persistence` and `JdbcTemplate` should rank above `Spring Data`

## Tests To Add

## Unit-level

1. candidate with focused retrieval -> `expected_response_state = normal`
2. candidate still broad -> `expected_response_state = needs_narrower_term`
3. candidate with no seed -> `expected_response_state = no_seed`

## Integration-level

1. blocked broad query returns reranked suggestions
2. reranked suggestions preserve original valid options
3. clearly broad candidates are not ranked first

## Why This Before Redis

Redis answers:

- what did we recommend before?
- what did users click?

But it does not answer:

- which candidate is best right now for this corpus and this retrieval pipeline?

That question is better solved by candidate-anchor evaluation first.

So the sequence should be:

1. rule-based candidate generation
2. retrieval-aware candidate ranking
3. only then optional Redis history / feedback

## Bottom Line

The candidate-anchor evaluator is the bridge between:

- semantic recommendation
- actual retrieval focus

That makes it the right next step before any cache or feedback layer.
