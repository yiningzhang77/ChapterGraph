2026-03-24 13:27

# Topic Membership Filter Plan

## Purpose

Insert a necessary stage between:

- Stage 1 Topic Discovery
- Topic DAG MVP

This stage exists to turn **raw topic candidates** into **clean topic descriptors**.

It is needed because Stage 1 currently proves:

- topic discovery can produce non-empty topic candidates
- but some graph components are too broad or too noisy to be treated as final user-facing topics

So before building topic-to-topic relations, the system must first clean the topic nodes themselves.

## Why This Stage Is Necessary

Stage 1 currently gives:

- singleton topics
- graph-component topics

But those are still raw graph groups.

They do not yet answer:

- which chapters are core members of the topic
- which chapters are only peripheral neighbors
- which chapters should be excluded
- which chapter should define the topic label
- whether the topic is too broad to expose directly

If Topic DAG is built directly on raw topic candidates, the graph structure will inherit noisy topic nodes.

That would make:

- topic recommendation weaker
- topic path quality worse
- study UI less trustworthy

## Core Idea

Reuse the **pattern** that already works in `/ask`:

- allow a broader first-pass retrieval/grouping layer
- then apply a second-pass filter

But do **not** reuse `/ask` evidence filter directly.

Why:

- `/ask` evidence filter is query-dependent
- topic membership filtering must be topic-dependent and stable across queries

So this stage needs a new filter:

**topic membership filter**

## Inputs

This stage should consume:

- Stage 1 `TopicCatalog`
- member chapter metadata
- `chapter_index_text`
- chapter titles
- optionally section/bullet-derived textual signals

It should not require:

- user query
- LLM decision-making
- topic-to-topic relations

## Outputs

This stage should produce refined topic descriptors such as:

```json
{
  "topic_id": "topic-data-persistence",
  "label": "Data Persistence",
  "description": "Cross-book topic around Spring data access and persistence implementation.",
  "core_chapter_ids": [
    "spring-in-action::ch3",
    "spring-start-here::ch12",
    "springboot-in-action::ch6"
  ],
  "peripheral_chapter_ids": [
    "spring-start-here::ch14"
  ],
  "excluded_chapter_ids": [
    "spring-in-action::ch15"
  ],
  "representative_chapter_id": "spring-in-action::ch3",
  "broad_topic_flag": false
}
```

This becomes the topic node layer for later Topic DAG work.

## Responsibilities

This stage should do four things.

## 1. Core vs Peripheral Membership

For each raw topic candidate, decide:

- which chapters are core members
- which chapters are peripheral members
- which chapters should be removed

This is the main job of the stage.

## 2. Representative Chapter Selection

For each cleaned topic, choose a stable representative chapter.

This representative chapter can later drive:

- topic label
- topic description
- entry chapter candidate
- debug explanation

## 3. Broad Topic Detection

Detect whether a raw topic candidate is too broad or too mixed.

Examples of warning signs:

- too many loosely related books/chapters
- multiple subthemes that do not belong together
- one topic candidate mixing conceptually separate chapter families

This stage should not necessarily solve broad topics perfectly.

But it should at least:

- mark them
- or split them conservatively if deterministic heuristics are strong enough

## 4. Quality Metadata

Each cleaned topic should expose quality-oriented metadata such as:

- `core_member_count`
- `peripheral_member_count`
- `broad_topic_flag`
- optional `quality_score`

This helps later UI and Topic DAG construction.

## Suggested Contracts

This stage likely needs new internal contracts.

## TopicMemberRole

Suggested values:

- `core`
- `peripheral`
- `excluded`

## TopicMembershipDecision

Suggested fields:

- `topic_id`
- `chapter_id`
- `member_role`
- `reason`
- optional `score`

## RefinedTopicDescriptor

Suggested fields:

- `topic_id`
- `label`
- `description`
- `core_chapter_ids`
- `peripheral_chapter_ids`
- `excluded_chapter_ids`
- `representative_chapter_id`
- `book_ids`
- `broad_topic_flag`

## RefinedTopicCatalog

Suggested fields:

- `run_id`
- `enrichment_version`
- `topics`

## Heuristic Strategy

The first version should remain deterministic.

## Heuristic 1: Representative Chapter Anchor

Pick a representative chapter first.

Candidate signals:

- earliest chapter order
- strongest textual centrality inside the candidate group
- best label quality

## Heuristic 2: Membership Scoring

Score each member chapter against the representative chapter using:

- title overlap
- `chapter_index_text` overlap
- optional section/bullet text overlap

This is closer to topic membership than raw edge score alone.

## Heuristic 3: Core Threshold

Chapters above a stricter internal similarity threshold become `core`.

## Heuristic 4: Peripheral Threshold

Chapters below core but still plausibly related become `peripheral`.

## Heuristic 5: Exclusion

Chapters with very weak support relative to the representative topic should be excluded.

This is how the mixed 8-chapter topic can eventually be cleaned.

## Why This Is Different From Topic Discovery

Stage 1 topic discovery asks:

- which chapters are graph-neighbors closely enough to form a candidate topic group?

Topic membership filtering asks:

- once a candidate topic exists, which chapters truly belong to it?

These are different problems.

That is why they should be separate stages.

## Why This Is Different From Topic DAG

Topic membership filtering asks:

- is this topic node itself clean?

Topic DAG asks:

- how should clean topic nodes connect to each other?

So Topic Membership Filter must happen before Topic DAG.

## Backend Shape

A practical implementation might look like:

- `feature_achievement/topic_study/membership_contracts.py`
- `feature_achievement/topic_study/membership_filter.py`

### `membership_contracts.py`

Owns:

- `TopicMemberRole`
- `TopicMembershipDecision`
- `RefinedTopicDescriptor`
- `RefinedTopicCatalog`

### `membership_filter.py`

Owns:

- representative chapter selection
- chapter-level membership scoring
- broad topic detection
- refined topic output

## Validation Strategy

This stage should be reviewed in two ways.

## 1. Focused Unit Tests

Verify:

- representative selection
- core/peripheral/excluded decisions
- broad-topic flag behavior

## 2. Real-DB Inspection

Run against current catalog and inspect:

- whether mixed topics become narrower
- whether obviously related chapters remain together
- whether labels become more trustworthy

## Current Validation Notes

Validated on the current real catalog for `run_id=5`.

Observed behavior:

- the broad mixed data topic is now still preserved as one refined topic node
- but it is explicitly marked with `broad_topic_flag=true`
- its representative chapter stabilizes on `spring-in-action::ch3`
- its members are split into:
  - `core`: data/persistence-oriented chapters
  - `peripheral`: looser neighbors such as actuator-adjacent or weaker persistence variants
- smaller, cleaner cross-book groups such as boot/configuration/rest remain unflagged

This is good enough for the next stage because Topic DAG can now consume:

- cleaner topic labels
- representative chapters
- explicit `core/peripheral/excluded` semantics
- an early warning when a topic node is still too broad

## Good Signs

- broad mixed topic groups get cleaner
- core chapter set feels coherent
- peripheral chapters are explainable
- representative chapter choice looks reasonable

## Bad Signs

- filter is too aggressive and destroys good cross-book topics
- everything collapses into singleton core sets
- broad-topic flag becomes meaningless because too many topics get flagged

## Success Criteria

This stage is complete when:

- raw topic candidates can be refined deterministically
- each topic has core/peripheral/excluded membership semantics
- representative chapters exist
- broad-topic detection exists
- the refined topic layer is stable enough to feed Topic DAG construction

## What This Enables Next

Once this stage is complete, Topic DAG work becomes much safer:

- Topic DAG edges connect cleaner topic nodes
- topic labels become more trustworthy
- entry-topic heuristics have better input
- frontend study graph is less likely to expose noisy topic groupings

## Bottom Line

Stage 1 finds candidate topics.

This stage decides which chapters actually belong to those topics strongly enough to make them usable.

That means:

- keep retrieval graph
- keep Stage 1 topic discovery
- add a second-pass topic membership filter
- only then build Topic DAG
