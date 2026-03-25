2026-03-25 09:52

# Topic DAG MVP Plan

## Purpose

Build the first user-facing study graph on top of topic discovery and topic membership filtering.

This stage does **not** replace the current retrieval graph.

Instead, it introduces a new graph layer:

- retrieval graph stays for `/ask`
- Topic DAG becomes the study navigation graph

## Why This Stage Exists

Stage 1 proved that the system can derive topic candidates from the current uploaded book set.

Topic membership filtering then proved that those raw candidates can be refined into cleaner topic nodes with:

- representative chapters
- core/peripheral/excluded membership
- broad-topic detection

But refined topic output is still not yet a user-facing study graph.

What is still missing:

- topic-to-topic relations
- user-facing study graph structure
- a graph shape appropriate for progress and recommendation

So the next step is not more topic grouping.

The next step is:

**turn refined topic output into a Topic DAG**

## Product Goal

The user should be able to see:

- what study topics exist
- which topics are foundational
- which topics come after which
- where they are currently focused
- what topic should come next

This is a learning graph, not a retrieval graph.

## Input To This Stage

This stage should consume:

- `RefinedTopicCatalog`
- current topic membership information
- deterministic heuristics for topic-to-topic relations

It should not depend on:

- free-form planner output
- model-generated relations
- user memory

## New Output Of This Stage

This stage should produce a typed `TopicDAG`.

Example:

```json
{
  "topics": [
    {
      "topic_id": "topic-spring-fundamentals",
      "label": "Spring Fundamentals"
    },
    {
      "topic_id": "topic-data-persistence",
      "label": "Data Persistence"
    }
  ],
  "relations": [
    {
      "from_topic_id": "topic-spring-fundamentals",
      "to_topic_id": "topic-data-persistence",
      "relation_type": "prerequisite",
      "reason": "Persistence chapters assume Spring application basics."
    }
  ],
  "entry_topic_ids": [
    "topic-spring-fundamentals"
  ]
}
```

## Scope

### In

- `TopicRelation`
- `TopicDAG`
- first deterministic topic relation heuristics
- first entry-topic heuristic
- frontend-ready graph shape

### Out

- personalized topic recommendation
- topic path inside a topic
- progress persistence
- dynamic replanning

## Current Refined Topic Review

The current refined catalog is usable enough to start DAG work, but only if the DAG builder is conservative.

Observed from the current real catalog:

- most topics are still singleton topics
- only a few cross-book topics are clearly clean enough to behave like stable study nodes
- one mixed data topic is explicitly marked with `broad_topic_flag=true`
- that broad topic should not be treated as a normal structural node in the first DAG pass

Current clean multi-chapter topics:

- `topic-3a1c6d37862d`
  - label: `1 Bootstarting Spring`
  - interpretation: fundamentals / getting started
- `topic-8bb8ba9cf63c`
  - label: `6 Working with configuration properties`
  - interpretation: configuration / app setup
- `topic-87ac96fd79f5`
  - label: `8 Securing REST`
  - interpretation: web security / REST security

Current broad topic:

- `topic-5157dcc55526`
  - label: `3 Working with data`
  - currently includes a reasonable data/persistence core but also a weaker peripheral tail
  - should be treated as a flagged topic node, not a strong prerequisite source or target in MVP

This means Topic DAG MVP should prefer:

- sparse structural edges
- clean topics over broad topics
- deterministic ordering based on foundationality and book-order support

It should avoid:

- forcing every topic into the DAG backbone
- treating flagged broad topics as trusted structural pivots

## New Contracts Needed

## TopicRelation

Represents one directed relation between topics.

Suggested fields:

- `from_topic_id`
- `to_topic_id`
- `relation_type`
- `reason`
- optional `score`

Suggested first relation types:

- `prerequisite`
- `recommended_next`
- `related`

## TopicDAG

Represents the whole study graph the frontend can render.

Suggested fields:

- `topics`
- `relations`
- `entry_topic_ids`

### Constraint

This structure should be acyclic in MVP.

If relation heuristics produce cycles, the builder should either:

- drop weak edges
- or downgrade them to non-structural metadata

## Topic Graph View Model

The frontend should eventually receive a shape that is easy to render.

That means the backend may also need a graph-fragment-like output, for example:

```json
{
  "nodes": [
    {
      "id": "topic-data-persistence",
      "label": "Data Persistence",
      "topic_size": 3
    }
  ],
  "edges": [
    {
      "source": "topic-spring-fundamentals",
      "target": "topic-data-persistence",
      "type": "prerequisite"
    }
  ]
}
```

## Relation Heuristic MVP

This stage should stay deterministic.

The first relation heuristics should be narrower than a generic all-topics graph.

### Heuristic 1: Foundational Before Specialized

If one topic is clearly broader and another is more implementation-specific, prefer:

- broad -> specific

### Heuristic 2: Lower Complexity Before Higher Complexity

If one topic's representative chapters look earlier/foundational and another looks later/deeper, prefer:

- earlier/foundational -> later/deeper

### Heuristic 3: Shared Book Ordering Signal

If two topics are represented inside the same book and one consistently appears earlier in chapter order, use that as a weak prerequisite hint.

### Heuristic 4: Cross-Book Overlap Support

If multiple books support the same directional relation, strengthen it.

### Heuristic 5: Broad Topic Downgrade

If a topic has `broad_topic_flag=true`, then in MVP:

- do not use it as a prerequisite source by default
- do not use it as a prerequisite target by default
- either:
  - leave it isolated in the topic graph
  - or attach it only with weak `related` edges

### Constraint

Do not try to solve full educational sequencing perfectly in this stage.

The goal is only to create a plausible, inspectable study DAG.

## First Practical Heuristic Set

Given the current refined catalog quality, the first real heuristic set should be conservative.

Recommended first pass:

1. only create `prerequisite` edges between non-broad topics
2. require at least one supporting signal:
   - book-order support
   - foundationality cue
   - topic label cue
3. if support is weak, do not create an edge
4. keep broad topics outside the structural backbone

The MVP DAG should be under-connected rather than over-connected.

That is the correct bias for a first user-facing study graph.

## Initial Foundationality Cues

The first deterministic cue set can be simple and inspectable.

Examples:

- labels containing:
  - `getting started`
  - `bootstarting`
  - `spring in the real world`
  - `fundamentals`
  are more foundational

- labels containing:
  - `configuration`
  - `web`
  - `rest`
  - `security`
  - `testing`
  - `deploying`
  are more specialized than the foundational topics above

- labels containing:
  - `securing`
  often come after the corresponding functional area
  - example: REST before Securing REST

## Entry Topic Bias

Based on the current refined review, the first entry-topic heuristic should strongly prefer:

- non-broad topics
- topics with no incoming prerequisite edges
- topics whose representative chapter is early in a book
- topics whose label looks foundational

This means the current likely entry candidates should come from:

- `Bootstarting Spring`
- `Spring in the real world`
- possibly other introductory singleton topics

## Relationship To Current Frontend

This stage should shift the main study UI away from the current chapter graph.

### Current chapter graph

Keep for:

- debug
- retrieval inspection
- topic membership inspection

### New Topic DAG

Use for:

- primary study navigation
- future progress highlighting
- future `next topic` recommendation

## Highlight Direction In This Stage

This stage does not need full progress tracking yet.

But it should leave a clean place for later highlight states such as:

- selected topic
- entry topic
- recommended next topic
- completed topic
- hotspot topic

That means Topic DAG nodes should already be stable long-lived identities.

## Backend Implementation Shape

This stage likely needs a new package layer such as:

- `feature_achievement/topic_study/dag_contracts.py`
- `feature_achievement/topic_study/dag_builder.py`

### `dag_contracts.py`

Owns:

- `TopicRelation`
- `TopicDAG`

### `dag_builder.py`

Owns:

- relation inference
- entry topic inference
- DAG construction
- cycle handling

## Validation Strategy

This stage should again be reviewed with real DB data, not just unit tests.

### Unit validation

- relation construction
- cycle prevention
- deterministic edge ordering

### Real-data validation

Inspect:

- topic count vs relation count
- whether obvious prerequisite directions look sane
- whether entry topics are plausible
- whether the graph is readable rather than over-connected
- whether broad topics stay out of the structural backbone

## Current Validation Notes

Validated on the current real catalog for `run_id=5`.

Observed behavior:

- `topic_count=29`
- `relation_count=17`
- `entry_topic_ids` currently resolve to:
  - `topic-3a1c6d37862d` (`Bootstarting Spring`)
  - `topic-d1a2f3c14a52` (`Spring in the real world`)
  - `topic-b67b8097aa3d` (`Understanding Spring Boot and Spring MVC`)
- `broad_topic_ids` currently contain:
  - `topic-5157dcc55526`
- `broad_structural_relation_count=0`

This confirms the current MVP bias is working:

- broad topics are present in the node layer
- but broad topics are not allowed to become structural hubs
- the resulting graph is still sparse enough to inspect manually

The current DAG is not yet a final educational sequence.

But it is already usable as a first study-navigation graph because:

- foundational topics emerge as entry candidates
- some plausible prerequisite edges appear
- the graph does not collapse into a dense cloud

## Good Signs

- the resulting graph is sparse enough to read
- foundational topics appear near the top
- deeper/specialized topics appear downstream
- the graph looks like a study map, not a chapter cloud
- broad flagged topics do not dominate the structure

## Bad Signs

- too many edges between nearly all topics
- cycles appear everywhere
- `related` edges dominate and drown structure
- entry topics are obviously not entry-level
- broad topics become central hubs

## Success Criteria

This stage is complete when:

- the system can build a typed `TopicDAG`
- topic nodes come from `RefinedTopicCatalog`
- topic relations are deterministic and inspectable
- entry topic ids are present
- the resulting DAG is suitable for frontend rendering
- broad topics are handled conservatively

## What This Enables Next

Once Topic DAG exists, the system can move cleanly into:

### Topic Catalog MVP

User-facing topic list and topic selection

### Topic Recommendation MVP

Map user intent to one or more DAG topics

### Topic Graph Highlight

Use DAG nodes as stable progress/highlight entities

### Topic Path MVP

Choose local traversal paths inside the DAG or inside one topic region

## Bottom Line

Stage 1 discovered topics.

Topic membership filtering cleaned those topic nodes enough for the next step.

This stage should turn those refined topics into the first real **study navigation graph**:

- stable topic nodes
- explicit topic relations
- entry topics
- frontend-ready DAG shape

That is the correct next layer after topic discovery and topic membership filtering and before recommendation/path/progress.
