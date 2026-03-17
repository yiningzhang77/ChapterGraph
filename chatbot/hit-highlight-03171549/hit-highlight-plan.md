2026-03-17 2pm

# Hit Highlight Plan

## Goal

Add graph-side visual feedback during `/ask` so the user can see which nodes were hit by the current request.

The intended experience is:

- nodes hit by the current term/chapter request become visually highlighted
- highlight intensity reflects hit strength
- hover reveals useful hit information
- later, repeated hits across the same session can accumulate

This should be built in three phases:

1. current-response highlight
2. session-level accumulated hit history
3. persisted memory / shared history

## Important Clarification

This feature does not require full memory on day one.

There are three different levels:

## Level A: response-driven highlight

- based only on the latest `/ask` response
- no memory required

## Level B: session-level hit accumulation

- counts repeated hits across multiple asks in the same browser session
- requires local frontend state
- does not require Redis

## Level C: persisted hit memory

- survives reloads or is shared across sessions/users
- requires a storage layer

So the right order is:

- first do response-driven highlight
- then do session accumulation
- only later add persistence

## Phase 1: Current-Response Highlight

## Objective

After each `/ask`, highlight graph nodes that participated in the current result.

This uses only the current response:

- `cluster`
- `seed.seed_chapter_ids`
- `evidence`

No memory is needed.

## Data Sources Already Available

The current `/ask` response already gives enough information:

- `cluster.seed.seed_chapter_ids`
- `cluster.chapters`
- `evidence.sections`
- `evidence.bullets`

These are enough to build a frontend-only highlight model.

## Highlight Semantics

Phase 1 should distinguish at least three node roles:

1. seed nodes
2. cluster-only nodes
3. evidence-backed nodes

Suggested interpretation:

- seed node:
  - explicitly matched or selected anchor
  - strongest base highlight

- cluster-only node:
  - reached through graph expansion
  - weaker highlight

- evidence-backed node:
  - appears in selected evidence bullets/sections
  - stronger than a plain cluster neighbor

## Suggested Scoring Model

Keep the first version simple and deterministic.

Example:

- seed hit: `+3`
- cluster membership: `+1`
- evidence section hit: `+1`
- evidence bullet hit: `+bullet_count`

Final score can be capped for rendering.

Example:

```text
score = min(7, seed_bonus + cluster_bonus + evidence_section_bonus + evidence_bullet_count)
```

The frontend does not need to persist this yet.

## Visual Design Direction

Use intensity, not just a binary border.

Suggested approach:

- keep existing node hue family by type if useful
- apply stronger fill / glow / ring intensity based on hit score
- seed nodes should look more dominant than plain cluster neighbors

Possible mapping:

- `score 0` -> default node color
- `score 1-2` -> light highlight
- `score 3-4` -> medium highlight
- `score 5+` -> strong highlight

This can be implemented as:

- adjusted fill color
- outer ring
- glow alpha

The exact rendering choice should follow the current graph rendering constraints.

## Hover Content For Phase 1

When the user hovers a highlighted node, show:

- `chapter_id`
- `book_id`
- `current_hit_score`
- `is_seed`
- `evidence_section_count`
- `evidence_bullet_count`

Optional:

- current query term
- query type

Example hover block:

```text
spring-in-action::ch3
Book: spring-in-action
Current hit score: 5
Seed hit: no
Evidence sections: 2
Evidence bullets: 6
```

## Frontend State Shape For Phase 1

Add a frontend-only map keyed by `chapter_id`.

Example:

```javascript
{
  "spring-in-action::ch3": {
    currentHitScore: 5,
    isSeed: false,
    evidenceSectionCount: 2,
    evidenceBulletCount: 6,
    queryType: "term",
    queryLabel: "JdbcTemplate"
  }
}
```

This state should be rebuilt after every successful `/ask`.

## Phase 1 Implementation Direction

Likely files:

- [app.js](C:/Users/hy/ChapterGraph/frontend/app.js)
- graph rendering code under `frontend/graph-core-dist/`

Suggested frontend helper:

```javascript
function buildAskHitMap(result) {
  ...
}
```

Then integrate that map into node rendering and hover rendering.

## Phase 1 Done When

- latest `/ask` visibly highlights participating nodes
- hover shows hit details from the current response
- no persistence is required

## Phase 2: Session-Level Accumulated Hit History

## Objective

Track repeated node hits across multiple asks during the same browser session.

This is the first real memory layer, but only at session scope.

It still does not require Redis.

## Why Phase 2 Matters

Once the user asks multiple related questions, repeated node hits become meaningful.

Examples:

- a node hit in three consecutive asks should look “hotter” than a one-off node
- hover should show both:
  - current request hit strength
  - accumulated session hit count

This makes the graph feel like an active workspace rather than a static background.

## Phase 2 State Model

Maintain a frontend session map:

```javascript
{
  "spring-in-action::ch3": {
    sessionHitCount: 4,
    lastHitAt: 1710000000000
  }
}
```

And combine it with Phase 1 current-response state:

```javascript
{
  "spring-in-action::ch3": {
    currentHitScore: 5,
    sessionHitCount: 4,
    ...
  }
}
```

## Accumulation Rule

After each successful `/ask`:

- for every currently hit chapter node
- increment `sessionHitCount`

Keep it simple.
No decay in the first version.

Possible later additions:

- decay
- time windows
- query-type weighting

Not needed now.

## Visual Semantics For Phase 2

Use two concepts:

1. current-hit intensity
2. session heat

Do not overload one channel if it becomes confusing.

Possible design:

- fill intensity = current request hit score
- outer ring or aura = session hit count

Or:

- current request uses hue
- session accumulation uses glow thickness

The main point is that the user can distinguish:

- hit now
- hit repeatedly over time

## Hover Content For Phase 2

Add:

- `session_hit_count`
- optionally `last_hit_at`

Example:

```text
spring-in-action::ch3
Current hit score: 5
Session hit count: 4
Evidence bullets: 6
```

## Phase 2 Done When

- repeated asks visibly accumulate node heat within the same browser session
- hover shows current-hit and session-hit data separately

## Phase 3: Persisted Memory / Shared History

## Objective

Persist hit history beyond a single browser session.

This can support:

- reload survival
- cross-device continuity
- multi-user analytics
- future agent/tool consumption

## Storage Options

Possible options, in increasing weight:

1. `localStorage`
2. backend trace table
3. Redis

Redis is only one option here.
It is not automatically the first or best one.

## When Persistence Is Actually Needed

Only add this when at least one of these becomes important:

- hit history should survive page reloads
- hit history should be shared across sessions
- backend tools need to read interaction history
- you want analytics over repeated node hits

If none of those matter yet, stay at Phase 2.

## What Phase 3 Might Store

Per chapter node:

- cumulative hit count
- recent hit count
- last hit timestamp
- recent triggering terms
- recent query types

Example shape:

```json
{
  "chapter_id": "spring-in-action::ch3",
  "hit_count": 17,
  "last_hit_at": "2026-03-17T12:34:56Z",
  "recent_terms": ["JdbcTemplate", "data persistence"]
}
```

## Why This Is Memory And Not Just UI

Phase 3 becomes memory because:

- state exists independently of the latest response
- state survives beyond the current page runtime
- state can later be consumed by backend logic or agent tools

That is different from Phase 1 and Phase 2.

## Suggested Implementation Order

## Commit A

- build current-response hit map
- add node highlight intensity for latest `/ask`
- add hover info for current hit data

## Commit B

- add session hit accumulation map in frontend state
- combine current-hit and session-hit data in rendering
- add hover info for session hit count

## Commit C

- choose persistence strategy only if needed
- keep it optional until there is a concrete product need

## Non-Goals

Do not mix this feature with:

- full conversational memory
- agent orchestration
- recommendation ranking
- Redis-first architecture
- backend semantic personalization

## Bottom Line

This feature should start as:

- response-driven graph highlight

Then evolve into:

- session-level accumulated hit visualization

Only later, if product needs justify it, should it become:

- persisted memory

That keeps the implementation cheap, useful, and well-scoped.
