2026-03-25 10:03

# Topic DAG MVP Commit List

This commit list implements [topic-dag-mvp-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/topic-dag-mvp-plan.md).

Scope:

- build a first deterministic `TopicDAG`
- consume `RefinedTopicCatalog`, not raw `TopicCatalog`
- keep the graph sparse and inspectable
- downgrade broad topics in the structural layer
- do not implement topic recommendation, path planning, or frontend migration yet

## Commit 01

`feat(topic-study): add topic dag contracts`

Status: `completed`

### Scope

Add the typed schema layer for Topic DAG.

### Suggested files

- `feature_achievement/topic_study/dag_contracts.py`

### Changes

- add `TopicRelationType`
- add `TopicRelation`
- add `TopicDAG`

### Constraint

Do not add builder logic yet.

## Commit 02

`feat(topic-study): add deterministic topic relation inference helpers`

Status: `completed`

### Scope

Add the first relation heuristics.

### Suggested files

- `feature_achievement/topic_study/dag_builder.py`

### Changes

- add foundationality cue helpers
- add shared-book ordering support heuristic
- add broad-topic downgrade rule
- infer candidate `TopicRelation` edges

### Constraint

Prefer under-connecting the graph over over-connecting it.

## Commit 03

`feat(topic-study): build typed topic dag from refined catalog`

Status: `completed`

### Scope

Turn refined topics plus inferred relations into a deterministic DAG.

### Changes

- build `TopicDAG` from `RefinedTopicCatalog`
- infer `entry_topic_ids`
- drop or downgrade cyclic/weak edges
- keep relation ordering deterministic

### Constraint

Do not add personalized traversal yet.

## Commit 04

`feat(topic-study): add real-db smoke script for topic dag`

Status: `completed`

### Scope

Validate the new DAG layer against the current real catalog.

### Suggested files

- `feature_achievement/scripts/smoke_topic_dag.py`

### Changes

- load refined topic catalog
- build topic DAG
- print topic count / relation count / entry topics
- print broad topics and whether they entered structural edges
- fail if DAG output is malformed

## Commit 05

`test(topic-study): add focused coverage for topic dag heuristics`

Status: `completed`

### Scope

Add unit tests for the deterministic DAG builder.

### Suggested files

- `tests/test_topic_dag.py`

### Changes

- test relation inference ordering
- test broad-topic downgrade
- test entry-topic selection
- test cycle prevention or weak-edge dropping
- test deterministic graph output

## Commit 06

`docs(topic-study): record topic dag mvp completion`

Status: `completed`

### Scope

Update docs once Topic DAG MVP is real.

### Changes

- update:
  - [topic-dag-mvp-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/topic-dag-mvp-plan.md)
- record current real-data DAG observations
- state what remains for topic recommendation/path/frontend

## Recommended Order

1. contracts
2. relation helpers
3. DAG build
4. smoke
5. tests
6. docs

## Stop Conditions

Stop and reassess if:

- broad topics become structural hubs
- the graph becomes dense enough to look like a cloud
- `related` edges dominate over structural edges
- entry topics become clearly implausible
- DAG construction starts depending on user-specific state

## Bottom Line

This stage is complete when:

- the system can build a typed `TopicDAG`
- it consumes `RefinedTopicCatalog`
- broad topics are handled conservatively
- entry topics are present
- the graph is sparse enough to serve as a study navigation layer
