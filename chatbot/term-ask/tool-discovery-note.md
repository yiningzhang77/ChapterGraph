# Tool Discovery Note

## Purpose

This note captures which parts of the current `/ask` logic already look like future tools for a ChapterGraph-style agent system.

The goal is not to redesign the system now.
The goal is to identify which rule-based pieces are worth keeping because they reveal future tool boundaries.

## Core Point

Writing rules now is not wasted work if the rules are treated as:

- explicit decision modules
- structured contracts
- failure-boundary experiments

That work becomes wasteful only if the rules stay scattered across router code and prompt code without a clear interface.

## What We Are Really Learning

The current `/ask` work is exposing a more important question:

What callable capabilities would a future ChapterGraph agent need?

That question cannot be answered abstractly.
It has to be discovered from real retrieval failures, real user questions, and real response-state boundaries.

## Candidate Future Tools

## 1. Retrieval Quality Evaluator

Current form:
- [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)

Current responsibility:
- decide whether term retrieval is normal, broad-blocked, or broad-allowed

Likely future tool contract:

```python
def evaluate_retrieval_quality(
    *,
    anchor_type: str,
    anchor_value: str,
    user_query: str,
    cluster: dict[str, object],
    evidence: dict[str, object] | None,
) -> dict[str, object]:
    ...
```

Potential output:

```json
{
  "state": "broad_blocked",
  "reason": "broad_term_precise_query",
  "term_too_broad": true,
  "evidence_too_scattered": true
}
```

Why it matters:
- this is already a decision tool
- it is corpus-agnostic at the state-machine level

## 2. Intent Classifier

Current form:
- embedded inside [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)

Current responsibility:
- distinguish definition-style questions from analytical questions

Likely future tool contract:

```python
def classify_question_intent(user_query: str) -> dict[str, object]:
    ...
```

Potential output:

```json
{
  "intent": "definition",
  "confidence": "rule_based"
}
```

Why it matters:
- future agents need this kind of gate before deciding whether to answer, ask for clarification, or narrow scope

## 3. Narrower Term Recommender

Current form:
- hardcoded suggestions in [retrieval_quality.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/retrieval_quality.py)

Current responsibility:
- suggest more specific follow-up terms when a broad term is blocked

Likely future tool contract:

```python
def suggest_narrower_terms(
    *,
    term: str,
    user_query: str,
    cluster: dict[str, object] | None = None,
    evidence: dict[str, object] | None = None,
) -> dict[str, object]:
    ...
```

Potential output:

```json
{
  "reason": "broad_term_precise_query",
  "suggested_terms": [
    "Spring Data",
    "data persistence",
    "JdbcTemplate",
    "Spring Data JPA"
  ],
  "confidence": "rule_based",
  "source": "corpus_specific_rules"
}
```

Why it matters:
- this is a strong candidate for a real future tool
- right now it is corpus-specific, but the interface can still be stable

## 4. Cluster Builder

Current form:
- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)

Current responsibility:
- build a term- or chapter-anchored retrieval cluster

Likely future tool contract:

```python
def build_cluster_for_anchor(
    *,
    anchor_type: str,
    anchor_value: str,
    run_id: int,
    enrichment_version: str,
) -> dict[str, object]:
    ...
```

Why it matters:
- this is already a tool in everything but name
- a future agent would call this before summarizing, narrowing, comparing, or planning

## 5. Evidence Focus Evaluator

Current form:
- implicit inside the retrieval-quality logic

Current responsibility:
- estimate whether evidence is focused enough for a precise answer

Likely future tool contract:

```python
def evaluate_evidence_focus(
    evidence: dict[str, object],
    cluster: dict[str, object],
) -> dict[str, object]:
    ...
```

Potential output:

```json
{
  "focus_state": "scattered",
  "chapter_count": 6,
  "book_count": 3
}
```

Why it matters:
- this can later guide clarification, decomposition, or answer-style downgrade

## 6. Controlled Answer Mode Selector

Current form:
- router-level branching in [ask.py](C:/Users/hy/ChapterGraph/feature_achievement/api/routers/ask.py)
- prompt downgrade in [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)

Current responsibility:
- choose between:
  - normal answer
  - blocked response
  - broad overview answer

Likely future tool contract:

```python
def choose_answer_mode(
    retrieval_state: dict[str, object] | None,
    user_query: str,
) -> dict[str, object]:
    ...
```

Why it matters:
- this is close to the policy layer an agent would need

## Two Layers Of Logic

To avoid overfitting to the current books, split logic into two layers.

## Layer A: Corpus-Agnostic Logic

These are safe to keep building now because they will likely survive later system changes.

Examples:
- broad retrieval detection
- scattered evidence detection
- intent classification
- blocked vs allowed state machine
- overview-only answer downgrade

These are future system tools or policies.

## Layer B: Corpus-Specific Heuristics

These are still useful, but they must be clearly isolated.

Examples:
- `spring -> Spring Boot / Spring MVC / Spring Data / Spring Security`
- `data -> JdbcTemplate / Spring Data JPA`

These are not universal logic.
They are current-corpus recommendation heuristics.

They should live in a dedicated module and return structured metadata that marks them as corpus-specific.

## What To Avoid

Do not let these rules become:

- inline `if/else` chains spread across router code
- prompt-only behavior without structured metadata
- book-specific hacks hidden inside generic modules

That would make later tool extraction harder.

## What To Do Instead

Prefer small modules with explicit contracts.

Good direction:

- `retrieval_quality.py`
- `intent_classifier.py`
- `term_recommender.py`
- `answer_mode.py`

Each should return structured output such as:

```json
{
  "state": "...",
  "reason": "...",
  "source": "rule_based",
  "confidence": "heuristic"
}
```

## Why This Is A Good Exploration Phase

The project is now in the best phase for tool discovery because:

- retrieval is real
- the graph is real
- the cluster/evidence path is real
- the LLM path is real
- failure cases are visible

That means every rule you add can be judged against actual behavior instead of hypothetical architecture.

This is exactly how useful tools are discovered:

1. a concrete failure appears
2. a small rule fixes or classifies it
3. the rule becomes a reusable module
4. the module later becomes a tool

## Recommended Next Step

If the next feature is smarter narrowing, the right sequence is:

1. add a dedicated `term_recommender.py`
2. keep the first version rule-based
3. return structured recommendation metadata
4. only later add Redis for caching or feedback

Redis should support the recommender, not define it.

## Bottom Line

Yes, this work is useful.

The value is not the hardcoded rules themselves.
The value is that they are revealing the actual tool surface a future ChapterGraph agent will need.
