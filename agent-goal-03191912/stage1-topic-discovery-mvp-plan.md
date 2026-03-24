2026-03-22 19:56

# Stage 1 Topic Discovery MVP Plan

Status: `completed`

## Purpose

Implement the first concrete step of the topic-study direction:

- derive topic candidates from the current fixed uploaded book set
- keep the logic deterministic
- reuse the current graph and enriched chapter data
- do not jump to topic recommendation or topic path yet

This stage is only about answering:

**What learnable topics exist in the current library?**

## Why This Stage Comes First

Before the system can:

- recommend a topic
- recommend where to start
- build a topic path

it first needs a stable and inspectable **topic inventory**.

Without topic discovery, all later steps become ad hoc:

- recommendation has nothing stable to recommend
- topic path has no topic unit to order
- topic-context `/ask` has no topic boundary

So Stage 1 is the foundation of the whole topic-oriented study flow.

## Scope

### In

- topic candidate discovery from current graph
- singleton topic handling
- connected-cluster topic handling
- initial topic metadata
- internal inspection / debug output

### Out

- user-facing topic picker UI
- user-intent to topic recommendation
- entry chapter recommendation
- ordered topic path
- topic-context `/ask`

## Product Output Of This Stage

This stage should produce an internal topic catalog that looks roughly like:

```json
{
  "topic_id": "topic-data-persistence",
  "label": "Data Persistence",
  "description": "Cross-book topic around data source usage and persistence access patterns.",
  "book_ids": [
    "spring-in-action",
    "spring-start-here",
    "springboot-in-action"
  ],
  "chapter_ids": [
    "spring-in-action::ch3",
    "spring-start-here::ch12",
    "springboot-in-action::ch6"
  ],
  "cluster_type": "graph_component",
  "seed_chapter_id": "spring-in-action::ch3"
}
```

This does not need to be exposed to the user yet.

It first needs to be inspectable by you.

## Data Sources

This stage should only depend on existing stable data:

- `run`
- `edge`
- `enriched_chapter`
- current chapter metadata already used by `/ask`

Specifically, it should use:

- graph connectivity from `edge`
- chapter titles
- `chapter_index_text`
- `sections[].bullets[]` only when needed for topic label / description quality

Do not introduce new ingestion or parsing work in this stage.

## Core Heuristic

The MVP should stay simple.

### Rule 1: Singleton Topic

If a chapter node has no meaningful cluster neighborhood under the selected run, it becomes a singleton topic.

Example:

- one chapter
- one topic
- the chapter title/index text becomes the first label source

### Rule 2: Connected Topic

If multiple nodes belong to the same connected component or near-component under the selected run, they form a shared topic candidate.

The first version can define this using the current graph as-is.

You do not need sophisticated community detection yet.

### Rule 3: Topic Labeling

The first label can be derived heuristically from:

1. highest-centrality or earliest chapter title
2. repeated phrase overlap across member chapter titles
3. fallback to a representative seed chapter title

This label can stay rough in MVP as long as it is inspectable.

### Rule 4: Topic Description

The first description can be assembled from:

- representative chapter titles
- representative `chapter_index_text`
- optional section/bullet snippets from top member chapters

It does not need LLM generation in MVP.

## New Internal Contracts Needed

This stage likely needs a small new contract layer.

### TopicDescriptor

Suggested fields:

- `topic_id`
- `label`
- `description`
- `cluster_type`
- `book_ids`
- `chapter_ids`
- `seed_chapter_id`

### TopicCatalog

Suggested fields:

- `run_id`
- `enrichment_version`
- `topics`

### TopicMembership

Suggested fields:

- `topic_id`
- `chapter_id`
- `membership_reason`
- `membership_score` if you want a weak confidence signal

These contracts should remain internal in Stage 1.

## Runtime / Execution Shape

This stage does not need a planner or agent loop.

It should still be structured as a deterministic execution flow:

1. load run-scoped graph slice
2. group chapters into topic candidates
3. build labels/descriptions
4. return `TopicCatalog`

That means the implementation should already be compatible with your runtime direction:

- explicit inputs
- explicit outputs
- inspectable intermediate state

## Recommended Implementation Shape

A practical first implementation could look like this:

### Module 1: topic contracts

Example:

- `feature_achievement/topic_study/contracts.py`

### Module 2: topic discovery service

Example:

- `feature_achievement/topic_study/discovery.py`

Responsibilities:

- fetch current run graph
- derive connected topic candidates
- create singleton topics
- build `TopicCatalog`

### Module 3: debug script / smoke script

Example:

- `feature_achievement/scripts/smoke_topic_discovery.py`

Responsibilities:

- choose a real run
- print topic count
- print several topic labels with member chapters
- fail clearly if no topics are produced

Delivered:

- `feature_achievement/topic_study/contracts.py`
- `feature_achievement/topic_study/discovery.py`
- `feature_achievement/scripts/smoke_topic_discovery.py`
- `tests/test_topic_discovery.py`

## Validation Strategy

This stage should be judged with real-DB inspection, not just unit tests.

### Unit validation

- grouping logic
- singleton handling
- label fallback behavior

### Real-DB validation

Use a real run and inspect:

- total topic count
- topic size distribution
- whether obvious cross-book topics are grouped together
- whether obviously unrelated clusters are wrongly merged

### Good signs

- singleton topics exist for isolated nodes
- multi-chapter topics exist for obvious shared topics
- labels are rough but understandable

### Bad signs

- almost everything collapses into one giant topic
- almost everything becomes singleton
- labels are so poor that the topic catalog is unusable

## Key Risks

### Risk 1: Edge graph is too noisy

If the current run graph is too loose, connected components may over-merge unrelated chapters.

Mitigation:

- use current edge score threshold
- allow a stricter topic-discovery threshold if needed

### Risk 2: Edge graph is too sparse

If graph connectivity is too weak, many useful cross-book topics may split into singletons.

Mitigation:

- allow one-hop neighborhood heuristics
- keep singleton fallback instead of forcing merge

### Risk 3: Topic labels are weak

Even if grouping is decent, labels may be poor.

Mitigation:

- keep labels deterministic first
- expose representative chapters in debug output
- improve naming only after grouping looks sane

## Success Criteria

Stage 1 is complete when:

- the system can derive a non-empty topic catalog from a real run
- singleton chapters become singleton topics
- obvious multi-chapter graph groups become shared topics
- each topic has at least:
  - id
  - label
  - member chapter ids
- there is a smoke/debug path to inspect topic discovery output

Validation:

```powershell
python -m pytest -q tests/test_topic_discovery.py
python -m feature_achievement.scripts.smoke_topic_discovery
```

Latest result:

- `4 passed`
- `topic_count=29`
- `singleton_count=25`
- `component_count=4`
- `smoke_topic_discovery passed`

## What This Stage Enables Next

Once this stage is complete, you can move cleanly to:

### Stage 2: Topic Catalog MVP

Expose the discovered topics to the user as a learnable topic list.

### Stage 3: Topic Recommendation MVP

Map user intent to one or more discovered topics.

### Stage 4: Topic Path MVP

Recommend where to start and what order to study inside one topic.

## Bottom Line

This stage should not try to be a planner.

It should only prove that the current ChapterGraph library can be turned into a usable **topic inventory** using:

- current run graph
- current enriched chapter data
- deterministic grouping heuristics

If this stage fails, later topic recommendation and path planning will not be stable.
