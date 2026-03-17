# llm-plan.md

Date: 2026-03-08  
Goal: Phase 2 - wire a real Qwen provider endpoint and validate whether current Cognitive Cluster + `chapter_text` is useful enough before changing enrichment again.

## 1. Ground truth from current repo

Already ready:

- `/ask` API + deterministic cluster builder are implemented and tested.
- Cluster payload already contains usable evidence units:
  - seed ids
  - chapter metadata (`chapter_id`, `book_id`, `title`)
  - bounded `chapter_text`
  - run-scoped edges + constraints
- Prompt scaffolding exists (`SYSTEM_PROMPT`, `build_prompt`).
- LLM adapter boundary exists (`ask_qwen`) and is already called from router.
- Failure path is non-breaking: provider errors are captured as `meta.llm_error`.
- Smoke script exists for full path: `feature_achievement/scripts/smoke_ask.py`.

Still missing:

- actual network call to Qwen-compatible API in `feature_achievement/llm/qwen_client.py`
- provider config validation (base URL, key, model)
- deterministic runtime settings for production path (timeout, retry, response checks)
- utility evaluation harness to judge answer usefulness against current cluster quality

## 2. Phase 2 objective (strict)

Do not redesign architecture. Keep existing flow:

`/ask -> build_cluster() -> ask_qwen() -> answer_markdown`

Phase 2 is complete only when:

1. real Qwen endpoint can be called from `/ask` with env config
2. cluster-grounded answers are returned for both term and chapter mode
3. we have evidence whether current `chapter_text` is enough for useful responses
4. we can decide enrichment changes based on measurements, not assumptions

## 3. Implementation plan

## 3.1 Step A - real provider integration in `qwen_client.py`

Files:

- `feature_achievement/llm/qwen_client.py`
- `config/llm.env.example`

Required envs (extend current template):

- `QWEN_PROVIDER=openai_compatible` (or similar explicit value)
- `QWEN_BASE_URL=https://...`
- `QWEN_API_KEY=...`
- `QWEN_MODEL=qwen...`
- optional: `QWEN_TEMPERATURE=0`, `QWEN_MAX_TOKENS=...`

Implementation notes:

- keep existing `stub` branch unchanged
- add one real provider branch only (no multi-agent abstractions)
- use a single request shape compatible with chat-completions style APIs
- enforce deterministic defaults:
  - temperature = 0
  - timeout from `llm_timeout_ms`
- fail with explicit error messages that router can expose in `meta.llm_error`

Minimal acceptance:

- with valid env, `/ask` returns non-empty `answer_markdown`
- with invalid env/key, `/ask` returns 200 + `meta.llm_error`

## 3.2 Step B - response quality guards (before enrichment changes)

Keep simple, but add hard checks in client layer:

- empty response check (`answer_markdown` must be non-empty)
- citation presence check (must contain `Citations` section or chapter ids)
- fallback message when model output is malformed

Reason:

- prevents silent success that is unusable for end users
- gives immediate signal whether prompt+cluster is sufficient

## 3.3 Step C - targeted evaluation pass with current data

Create a lightweight eval script (or extend smoke) that runs fixed prompts on current DB/run:

- 10 term queries (e.g., actuator, security, data source, transaction)
- 10 chapter queries (selected known chapter_ids)

Per query record:

- seed count
- chapter count
- edge count
- answer length
- citation count
- whether citations map to returned cluster chapter_ids

Output to `tmp/llm_eval_report.json`.

This must run before any enrichment redesign.

## 4. Risks in current enrichment logic (unchanged today)

Current enrichment behavior (`feature_achievement/enrichment.py`):

- `chapter_text` = bullets joined, else sections joined
- no full prose
- no semantic compression beyond simple concatenation

Risks for LLM usefulness:

- shallow evidence: good for topic identification, weak for deep explanation
- missing fine-grained facts (definitions, caveats, examples)
- possible lexical bias (term-heavy chapters dominate seed retrieval)

Important: these are hypotheses. We should verify with measured failure cases first, not change enrichment preemptively.

## 5. What to validate first (decision gate)

Before touching enrichment logic again, validate these 4 gates:

1. Connectivity gate: real endpoint stability
   - success rate over N test asks
   - timeout/error rate

2. Grounding gate: citation fidelity
   - citations must refer to cluster chapter_ids
   - no uncited major claims

3. Utility gate: answer usefulness with current cluster
   - short human rating per query (useful / partially useful / not useful)
   - capture failure reasons

4. Retrieval sufficiency gate: cluster quality vs answer quality
   - when answers fail, check if cluster lacked needed evidence or model failed to use evidence

Decision rule:

- If most failures are "cluster lacked evidence", improve enrichment/retrieval.
- If most failures are "model ignored evidence", adjust prompt/client constraints first.

## 6. Proposed deliverables for Phase 2

1. `feat(llm): wire real qwen provider endpoint`
   - implement real provider branch in `qwen_client.py`
   - extend `config/llm.env.example`

2. `test(llm): add integration-safe client tests`
   - unit tests for config validation, stub branch, malformed output handling
   - keep external calls mocked

3. `feat(eval): add llm usefulness evaluation script`
   - script that runs fixed ask set and writes `tmp/llm_eval_report.json`

4. `docs(llm): document provider setup and validation checklist`
   - update README with real provider setup and eval run instructions

## 7. Phase 2 exit criteria

Phase 2 is done when all are true:

- `/ask` works with real Qwen endpoint for both term/chapter mode
- failures are observable via `meta.llm_error` and logs
- eval report exists and shows citation-grounded outputs
- we have a clear evidence-based conclusion:
  - "current cluster/chapter_text is sufficient for MVP usefulness" or
  - "specific enrichment gaps confirmed, with examples"

This keeps priority on completing the RAG -> ChatBot cycle on the existing Graph-RAG foundation.
