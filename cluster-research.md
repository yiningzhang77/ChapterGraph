# cluster-research.md

Date: 2026-03-09  
Scope: evaluate "cluster as index layer" and define how to evolve from `chapter_id -> chapter_text -> section -> bullet -> 原文 -> LLM`.

## 0. Direct answer

Your direction is feasible and practical.

- Yes: treat current `cluster` as **index/retrieval layer**, not final evidence layer.
- Yes: keep `chapter_text` for coarse recall, then do hierarchical drill-down to section/bullet/source before LLM.
- Key condition: current repo does **not** yet store usable "原文" chunks (only TOC-like content and bullets/sections). To reach the last step, you need a source-chunk layer.

## 1. Current state (grounded in repo)

From current code:

- `enrichment.py`: `chapter_text = " ".join(bullets) if bullets else " ".join(sections)`
- `ingestion.py`: bullets and sections are parsed from TOC-like files; numeric prefixes are effectively removed from section titles in parsing.
- `cluster_builder.py`: cluster currently returns chapter-level objects only (`chapter_id`, `book_id`, `title`, `chapter_text`) + edges.
- `EnrichedChapter` model already stores:
  - `chapter_text` (string)
  - `sections` (JSON list)
  - `signals` (JSON, includes `bullets`, currently `raw_text` empty)

Interpretation:

- You already have a good **chapter-level index payload**.
- You already have raw materials for section/bullet-level reranking.
- You do **not** yet have reliable full-source evidence slices ("原文").

## 2. If cluster is only index layer, what is the follow-up path?

Use a 4-stage retrieval chain:

1. **Chapter stage (coarse retrieval)**
   - Input: user query
   - Search: current `chapter_text` / future vector + keyword
   - Output: top chapter_ids with scores

2. **Section stage (intra-chapter localization)**
   - For each hit chapter, score `sections[]` against query
   - Keep top sections per chapter

3. **Bullet stage (fine localization)**
   - For each selected section, score its bullets
   - Keep top bullets

4. **Source stage (ground truth evidence)**
   - Map selected bullets to source chunks (`source_chunk_id` / file offsets / paragraph ids)
   - Pull source snippets
   - Build final LLM context from snippets + minimal metadata

Then:

- LLM consumes **evidence bundle**, not raw chapter_text blob.
- cluster response can keep index-level info + optional `evidence_preview`.

## 3. How to achieve this in this repo (incremental, no redesign)

## 3.1 Data shape additions (minimal-first)

Keep existing tables; add structure first in JSON, then normalize later only if needed.

Recommended enriched chapter JSON shape:

```json
{
  "id": "spring-in-action::ch3",
  "title": "Working with data",
  "chapter_index_text": "...",
  "sections": [
    {
      "section_id": "spring-in-action::ch3::s1",
      "title_raw": "3.1 Reading and writing data with JDBC",
      "title_norm": "Reading and writing data with JDBC",
      "order": 1,
      "bullets": [
        {
          "bullet_id": "spring-in-action::ch3::s1::b1",
          "text_raw": "3.1.1 Working with JdbcTemplate",
          "text_norm": "Working with JdbcTemplate",
          "order": 1,
          "source_refs": ["src:book/spring-in-action/ch3#p12:34-12:40"]
        }
      ]
    }
  ],
  "signals": {
    "bullets_flat_norm": ["..."],
    "raw_text": "...optional raw source..."
  }
}
```

If you do not want deep DB migration now:

- keep `EnrichedChapter.sections` as JSON objects (instead of pure string list)
- keep `signals` as JSON for flat bullet lists + source refs

## 3.2 Retrieval implementation additions

Add 3 helper layers under `feature_achievement/db/ask_queries.py`:

- `rank_sections(chapter_id, query, top_k)`
- `rank_bullets(chapter_id, section_ids, query, top_k)`
- `fetch_source_chunks(source_refs, token_budget)`

Scoring can start lexical (ILIKE/TF-IDF), then move to embeddings.

Pseudo flow inside `/ask`:

```text
cluster = build_cluster(...)                # chapter-level index hits
focus = localize_with_sections(cluster)     # section top-k per chapter
points = localize_with_bullets(focus)       # bullet top-k
evidence = load_source_snippets(points)     # source chunks
answer = ask_qwen(query, evidence)
```

## 3.3 Response contract evolution (backward compatible)

Keep current `cluster` for compatibility; add optional evidence block:

```json
{
  "cluster": { "chapters": [...], "edges": [...] },
  "evidence": {
    "sections": [...],
    "bullets": [...],
    "source_snippets": [...]
  }
}
```

Front-end can stay unchanged at first.

## 4. What should change in `chapter_text` to fit this shape?

Current `chapter_text` is a flattened string, good for coarse retrieval but weak for localization.

Recommended change: split semantics into 2 fields.

## 4.1 Keep a dedicated index string

- Keep chapter-level searchable text, but formalize it as `chapter_index_text`.
- Include normalized section/bullet text in deterministic format.

Example:

```text
section:reading and writing data with jdbc
bullet:working with jdbctemplate
bullet:defining a schema and preloading data
...
```

Why:

- still fast for coarse retrieval
- gives more controlled tokens than free concatenation

## 4.2 Preserve structure + raw forms separately

For each section/bullet keep both:

- `*_raw` (with numbering like `2.3.2`, useful for traceability)
- `*_norm` (without numbering, useful for retrieval)

Do not rely on one flattened string to do both jobs.

## 4.3 Preserve source mapping metadata

Each bullet should carry `source_refs` (or equivalent IDs), so final evidence can be pulled deterministically.

Without this mapping, "bullet -> 原文" cannot be guaranteed.

## 5. Practical rollout plan

## Phase A (fast, low risk)

- Keep current cluster API.
- Change enrichment output so `sections` become structured objects and bullets attach to sections.
- Add `chapter_index_text` while keeping `chapter_text` for compatibility.

Acceptance:

- current `/ask` still works
- chapter/section/bullet IDs stable

## Phase B (localization)

- Add section/bullet ranking in backend.
- Add optional `evidence` payload in `/ask` response.

Acceptance:

- same query can return top sections/bullets with scores
- citations can reference bullet_id or section_id

## Phase C (source-grounded)

- Introduce source chunk store (from real text, not only TOC).
- Implement bullet -> source chunk mapping and snippet budgeting.

Acceptance:

- each answer citation can link to snippet-level evidence
- model answers improve on nuanced questions

## 6. Major risk to call out now

Current data is mostly TOC-level signals. If "原文" means full chapter prose, this repo currently does not ingest/store it.

So the real gating question is not cluster logic; it is source availability:

- If only TOC exists, you can reach section/bullet granularity but not true paragraph-level grounding.
- If you ingest chapter prose (or selected excerpts), the proposed chain becomes fully achievable.

## 7. Bottom line

Your idea is right for this project stage:

- `cluster` should be treated as index layer.
- `chapter_text` should become an index-specific field, not the final evidence carrier.
- add hierarchical structure + source refs, then drill down before LLM.

This gives you a controlled path from current MVP to evidence-grounded chat without redesigning the whole system.
