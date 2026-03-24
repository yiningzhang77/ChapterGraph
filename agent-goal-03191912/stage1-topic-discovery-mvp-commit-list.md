2026-03-22 00:09

# Stage 1 Topic Discovery MVP Commit List

This commit list implements [stage1-topic-discovery-mvp-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/stage1-topic-discovery-mvp-plan.md).

Scope:

- derive topic candidates from the current fixed book graph
- stay deterministic
- stay inspectable
- do not implement topic recommendation yet
- do not implement topic path yet

## Commit 01

`feat(topic-study): add topic discovery contracts`

Status: `completed`

### Scope

Add the minimum internal schema layer for topic discovery.

### Suggested files

- `feature_achievement/topic_study/contracts.py`

### Changes

- add `TopicDescriptor`
- add `TopicCatalog`
- add `TopicMembership`
- add `cluster_type` / related literals if needed

### Constraint

Do not add discovery behavior yet.

## Commit 02

`feat(topic-study): add graph grouping helpers for topic candidates`

Status: `completed`

### Scope

Add the pure grouping logic before wiring real DB access.

### Suggested files

- `feature_achievement/topic_study/discovery.py`

### Changes

- add singleton topic handling
- add connected-group topic handling
- add deterministic topic id generation

### Goal

Be able to turn a graph slice into topic candidate groups without touching naming quality yet.

## Commit 03

`feat(topic-study): build topic catalog from current run data`

Status: `completed`

### Scope

Wire the discovery logic to real current data.

### Changes

- load run-scoped graph data
- load chapter metadata needed for topic labeling
- produce `TopicCatalog`
- add first-pass labels and descriptions

### Constraint

Keep labeling heuristic and inspectable.

## Commit 04

`feat(topic-study): add real-db smoke script for topic discovery`

Status: `completed`

### Scope

Add a script that validates topic discovery against the current DB.

### Suggested files

- `feature_achievement/scripts/smoke_topic_discovery.py`

### Changes

- find a current run
- build topic catalog
- print topic count
- print a few sample topics with member chapters
- fail clearly if catalog is empty or malformed

## Commit 05

`test(topic-study): add focused coverage for topic discovery heuristics`

Status: `completed`

### Scope

Add unit coverage for the deterministic grouping layer.

### Suggested files

- `tests/test_topic_discovery.py`

### Changes

- test singleton topic creation
- test connected chapter grouping
- test deterministic topic id generation
- test label fallback behavior

## Commit 06

`docs(topic-study): record stage1 topic discovery completion`

Status: `completed`

### Scope

Update the stage plan once the implementation exists.

### Changes

- mark completion in:
  - [stage1-topic-discovery-mvp-plan.md](C:/Users/hy/ChapterGraph/agent-goal-03191912/stage1-topic-discovery-mvp-plan.md)
- add validation notes
- note what is intentionally deferred to Stage 2+

## Recommended Order

1. contracts
2. grouping helpers
3. real run-backed catalog build
4. smoke script
5. focused tests
6. doc update

## Stop Conditions

Stop and reassess if:

- topic discovery starts embedding recommendation logic
- grouping becomes opaque or model-dependent too early
- almost all chapters collapse into one topic with no debugging path
- almost all chapters become singleton without any clear threshold reasoning

## Bottom Line

This stage is complete when:

- the system can derive a non-empty `TopicCatalog` from a real run
- the catalog is based on explicit `TopicDescriptor` contracts
- there is a smoke/debug path to inspect topic discovery quality
