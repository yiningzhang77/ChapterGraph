# make_better.md

Goal: improve answer quality on the current `/ask` chatbot without redesigning the system.

Current problems already observed:

- Chinese answers sometimes produce mixed-script technical terms such as `控roller`
- chapter-mode answers are often less complete than term-mode answers
- chapter-mode currently does not dig deeply enough into ordered bullets

This document focuses on the next practical improvements.

## 1. Improve prompt behavior first

Primary file:

- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)

Current prompt is too generic:

- it says "Only use facts from the provided cluster JSON"
- but it does not strongly control output language
- it does not control technical-term style
- it does not distinguish term-mode and chapter-mode answer expectations

## 1.1 What to change

Add explicit response rules to `SYSTEM_PROMPT`:

- answer in the same language as the user query
- if the user asks in Chinese, answer in Chinese
- for technical terms, either:
  - keep the English term
  - or use `Chinese (English)`
- never invent mixed-script partial translations such as `控roller`
- prefer section/bullet evidence over vague chapter summary
- if evidence is thin, say so instead of expanding from prior knowledge

## 1.2 Prompt contract by query type

The prompt should distinguish:

- `term`
  - explain the concept
  - summarize related chapters
  - connect evidence across chapters if present
- `chapter`
  - summarize the selected chapter in a structured way
  - prioritize main sections and important bullets from that chapter
  - only use neighbor chapters as supplemental context

## 1.3 Recommended prompt direction

Add instructions such as:

```text
Follow the user's language.
If the user asks in Chinese, answer in Chinese.
For technical terms, either keep the original English term or write Chinese followed by English in parentheses.
Do not create mixed-script partial translations such as "控roller".

If query_type=chapter:
- treat the selected chapter as the primary source
- summarize the chapter by major sections first
- then include important implementation/details from bullet evidence
- use neighbor chapters only as secondary context
```

## 1.4 Why prompt change alone is not enough

Prompt fixes wording quality, but it will not fully solve chapter-mode thinness.

That problem mostly comes from retrieval/evidence assembly.

## 2. Make chapter-mode evidence dig into bullets

Primary file:

- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)

Current problem:

- `_build_evidence()` is optimized for lexical overlap with the user query
- this works reasonably for term-mode
- it is weak for chapter-mode prompts such as:
  - `为我讲解这章相关内容`
  - `Summarize this chapter`

Those queries contain little topical signal, so bullet ranking becomes too shallow.

## 2.1 Current weakness

Current scoring is roughly:

- score section by query-token overlap
- score bullet by query-token overlap
- take top `section_top_k` and `bullet_top_k`

This means chapter-mode can miss:

- the main ordered structure of the chapter
- important bullets that do not lexically match the user wording
- full chapter coverage when the query is generic

## 2.2 What chapter-mode should do instead

For `query_type == "chapter"`:

- treat the selected chapter as the primary evidence source
- prefer ordered coverage over lexical overlap
- walk selected chapter `sections[]` in `order`
- walk selected chapter `bullets[]` in `order`
- fill evidence budget from the selected chapter first
- only then use expanded neighbor chapters as supplemental evidence

This is the key quality change.

## 2.3 Recommended evidence policy

For chapter-mode:

1. selected chapter sections first
2. selected chapter bullets first
3. preserve section order
4. preserve bullet order
5. only use neighbor chapter evidence after the selected chapter budget is satisfied

Practical implementation shape:

- if `req.query_type == "chapter"`:
  - detect `primary_chapter_id = seed_ids[0]`
  - build evidence rows from all `sections[]` and `bullets[]`
  - split those evidence rows into:
    - primary chapter rows
    - neighbor rows
  - sort primary chapter section rows by `section_order`
  - sort primary chapter bullet rows by `section_order`, then `bullet_order`
  - fill `section_top_k` and `bullet_top_k` from primary chapter first
  - backfill with neighbor rows only if space remains

## 2.4 Minimal code strategy

Do not rewrite the whole cluster builder.

Instead:

- keep the existing cluster construction and hop expansion
- only branch inside `_build_evidence()`
- add a chapter-mode path that uses structural order instead of query-overlap ranking as the main rule

## 2.5 Extra detail worth adding to evidence rows

To support better chapter-mode ordering, include these transient fields while building evidence:

- `section_order`
- `bullet_order`
- `is_primary_chapter`

These do not need to become permanent DB fields.
They can be derived from `sections` JSON during evidence assembly.

## 3. Suggested implementation sequence

## 3.1 Commit A: prompt quality

Status: completed

Change:

- [prompts.py](C:/Users/hy/ChapterGraph/feature_achievement/llm/prompts.py)

Add:

- language-following rule
- technical-term style rule
- chapter-mode instruction block

Acceptance:

- Chinese answers stop producing mixed-script terms like `控roller`
- citations still appear

## 3.2 Commit B: chapter evidence drill-down

Status: completed

Change:

- [cluster_builder.py](C:/Users/hy/ChapterGraph/feature_achievement/ask/cluster_builder.py)

Add:

- chapter-mode specific evidence ordering
- selected-chapter-first section fill
- selected-chapter-first bullet fill
- neighbor evidence only as secondary fill

Acceptance:

- chapter ask becomes more complete
- chapter ask better reflects actual section structure
- important bullets from the selected chapter appear more often in the answer

## 3.3 Commit C: tests

Status: pending

Add focused tests for:

- chapter-mode evidence favors selected chapter
- chapter-mode evidence preserves order
- term-mode behavior does not regress
- prompt includes language/term-style rules

Suggested files:

- [test_ask_cluster_builder.py](C:/Users/hy/ChapterGraph/tests/test_ask_cluster_builder.py)
- [test_qwen_prompts.py](C:/Users/hy/ChapterGraph/tests/test_qwen_prompts.py)

## 4. What not to change yet

Avoid these for now:

- redesigning `enriched_chapter`
- splitting sections/bullets into new DB tables
- adding agent orchestration
- changing graph expansion semantics

Those are not necessary to fix the current answer quality issues.

## 5. Definition of better

This round is successful if:

- Chinese answers use cleaner terminology
- chapter-mode answers become more chapter-structured
- chapter-mode answers cite the selected chapter more heavily
- term-mode remains broad and cross-chapter when appropriate
- all tests still pass
