# cluster-phase1-discuss.md

Date: 2026-03-09  
Topic: How to guarantee hierarchical recall (`term -> chapter_index_text -> section -> bullet -> source_refs`) while keeping the current logic mostly unchanged.

## 1. Problem framing

Constraint you gave:

- Keep current ask flow logic basically unchanged.
- Only replace coarse field from `chapter_text` to `chapter_index_text`.
- Next step should reliably recall section/bullet/source_refs after chapter recall.

Current reality:

- Existing chapter recall is DB-based (`term` search in enriched chapter rows).
- Current old JSON shape (`sections: list[str]`, `signals.bullets: list[str]`) does not preserve section->bullet mapping.
- To support robust hierarchical recall, we need structured `sections[].bullets[]`.

## 2. What does "guarantee recall" actually mean?

For this pipeline, "guarantee" means:

1. deterministic candidate generation (same input -> same section/bullet candidates)
2. stable ranking method (explicit scoring, no hidden randomness)
3. bounded latency and bounded token output
4. graceful behavior when `source_refs` is null

So the main design question is not "hardcode SQL or not"; it is where each stage should execute for best tradeoff.

## 3. Recommended retrieval architecture (for your constraint)

## 3.1 Stage A: term -> chapter (already DB search)

Keep exactly the current style, just switch field:

- from: `ILIKE(chapter_text)`
- to: `ILIKE(chapter_index_text)`

This is your coarse recall gate.

## 3.2 Stage B: chapter -> section

Recommended in Phase-1:

- fetch selected chapters once from DB (already done in cluster builder)
- do section localization **in application memory** on structured JSON fields

Why this is better now:

- avoids expensive JSONB unnest SQL in first iteration
- no complex migration to fully normalized section tables yet
- deterministic and easy to test

## 3.3 Stage C: section -> bullet

Same strategy in Phase-1:

- run bullet scoring in memory from `sections[].bullets[]`
- keep top-k bullets per chapter (or per section)

## 3.4 Stage D: bullet -> source_refs

Phase-1 rule:

- return `source_refs` as-is (nullable)
- if null, keep output shape but skip source snippet fetch

Phase-2 rule (after you fill refs):

- map `source_refs -> source_chunk table` and fetch snippets by IDs

## 4. DB query vs in-memory: what should be used now?

## 4.1 Option A: DB-hard SQL for section/bullet immediately

Example style:

- use PostgreSQL `jsonb_array_elements` / lateral joins
- compute ranking in SQL

Pros:

- can scale with proper indexing later

Cons:

- high complexity now
- harder to debug and test
- JSONB ranking queries become heavy quickly

## 4.2 Option B: in-memory hierarchical localization (recommended now)

Flow:

1. DB returns top chapter rows (small set, e.g. <= 20)
2. app ranks sections/bullets inside those chapters
3. return evidence candidates

Pros:

- minimal disruption to existing logic
- deterministic and easy to iterate
- no premature schema over-design

Cons:

- if top chapter set becomes very large, CPU work grows

For current project scale, Option B is the best immediate choice.

## 4.3 Option C: normalized DB tables for section/bullet (future)

When scale grows, add tables:

- `enriched_section(chapter_id, section_id, order, title_norm, ... )`
- `enriched_bullet(chapter_id, section_id, bullet_id, order, text_norm, source_refs, ... )`

Then stage B/C can move to indexed SQL search.

Conclusion:

- **Now**: Option B
- **Later**: move to Option C when data/traffic justifies

## 5. Practical scoring method (deterministic)

Use one shared normalizer and token scorer.

Section score example:

- `score = 0.7 * sim(query, section.title_norm) + 0.3 * max_sim(query, bullet.text_norm in section)`

Bullet score example:

- `score = sim(query, bullet.text_norm)`

Where `sim` can be simple and deterministic:

- token overlap / BM25-like lexical score
- or trigram similarity

Do not start with LLM-based reranking here; keep this layer purely deterministic.

## 6. How to wire this without changing current ask shape too much

Current:

- cluster builder returns chapter-level `cluster`

Minimal extension:

- keep `cluster` as index object
- add optional `evidence` object:
  - `evidence.sections[]`
  - `evidence.bullets[]`
  - each bullet includes `source_refs` (nullable)

No need to redesign API around agents/tools.

## 7. Can numbering like `3.2.3` help performance?

Short answer:

- **Yes, but indirectly**.
- It is not a semantic retrieval signal by itself.

## 7.1 What numbering helps with

1. deterministic IDs and ordering
   - easy stable sort and reproducible outputs

2. fast direct addressing
   - if user mentions "section 3.2" or "bullet 3.2.3", mapping is immediate

3. pruning inside chapter
   - if one section is selected, bullets can be limited by section path

4. cheap joins in normalized schema
   - store `chapter_order`, `section_order`, `bullet_order` ints for indexed filtering

## 7.2 What numbering does NOT help much

- It does not improve lexical term relevance for topic queries
- Storing `"3.2.3"` as plain text alone gives limited index benefit

## 7.3 Recommended usage of numbering

Keep both:

- `*_raw` with original numbering text (traceability)
- parsed numeric order fields:
  - `section_order: int`
  - `bullet_order: int`

If you later normalize DB tables, index by:

- `(chapter_id, section_order)`
- `(chapter_id, section_id, bullet_order)`

This improves retrieval speed for structural operations, not semantic relevance.

## 8. Proposed concrete Phase-1 execution decision

1. Switch coarse search to `chapter_index_text` in DB.
2. Ensure enriched JSON is structured (`sections[].bullets[]`) and no `signals` dependency.
3. Implement section/bullet localization in app layer (deterministic scorer).
4. Return `source_refs` nullable now; do not block on source chunk system.
5. Add tests for deterministic ranking and null `source_refs` behavior.

This gives a guaranteed hierarchical recall path with minimal architectural disruption.

## 9. Risk checklist

1. If section->bullet mapping is not preserved in data, hierarchical recall quality will be fake.
2. If normalization is inconsistent between indexing and query, recall quality drops sharply.
3. If top chapter set is too large, in-memory localization latency may spike.
4. If `source_refs` stays null too long, LLM grounding quality remains limited at bullet text level.

## 10. Bottom line

- Do chapter recall in DB (`chapter_index_text`) as you already do.
- Do section/bullet recall in memory first, not hardcoded complex SQL.
- Use numbering (`3.2.3`) for structure and routing efficiency, not as semantic signal.
- Keep `source_refs` nullable now, but keep field required in schema so next step is smooth.
