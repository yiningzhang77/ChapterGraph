# ask-commit-list.md

Date: 2026-03-07  
Goal: 按 `ask-plan.md` 落地 `/ask` MVP（term + chapter + LLM 对话）

## [x] Commit 01 - `chore(db): normalize enrichment_version to v1_bullets+sections`

Purpose:
- 统一 `run` / `enriched_chapter` 版本命名，消除 Blocker A。

Changes:
- add `feature_achievement/scripts/normalize_enrichment_version.py`

Run:
- `python -m feature_achievement.scripts.normalize_enrichment_version`

Verify:
- SQL 验证两张表仅有 `v1_bullets+sections`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 02 - `feat(api): add /ask request-response schema and runtime version guard`

Purpose:
- 先建 `/ask` API 外壳，包含默认版本和 `409` mismatch 规则。

Changes:
- add `feature_achievement/api/schemas/ask.py`
- add `feature_achievement/api/schemas/__init__.py`
- add `feature_achievement/api/routers/ask.py`
- update `feature_achievement/api/main.py` (mount ask router)

Verify:
- `GET /openapi.json` 出现 `/ask`
- mismatch 请求返回 `409`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [x] Commit 03 - `feat(cluster): implement deterministic cluster builder (ilike path, hop2)`

Purpose:
- 实现 MVP 核心：term/chapter -> seed -> hop2 -> cluster。

Changes:
- add `feature_achievement/ask/__init__.py`
- add `feature_achievement/ask/cluster_builder.py`
- add `feature_achievement/db/ask_queries.py`
- update `feature_achievement/api/routers/ask.py` (use builder)

Verify:
- term 请求有 `cluster.chapters` / `cluster.edges`
- chapter 请求可通过 `chapter_id` 出结果
- `$env:PYTHONPATH='.'; pytest -q`

---

## [ ] Commit 04 - `feat(llm): add constrained prompt and qwen adapter (stub first)`

Purpose:
- 打通 LLM 调用链，先 stub 可跑，再切真实 provider。

Changes:
- add `feature_achievement/llm/__init__.py`
- add `feature_achievement/llm/prompts.py`
- add `feature_achievement/llm/qwen_client.py`
- update `feature_achievement/api/routers/ask.py` (llm_enabled flow)

Verify:
- `llm_enabled=true` 返回 `answer_markdown`（stub）
- provider异常时返回 `meta.llm_error`
- `$env:PYTHONPATH='.'; pytest -q`

---

## [ ] Commit 05 - `feat(config): add LLM config template for API key`

Purpose:
- 给你留密钥配置文件模板，不提交真实密钥。

Changes:
- add `config/llm.env.example`
- update `.gitignore` (ignore `config/llm.env`)
- optional: update `feature_achievement/llm/qwen_client.py` (load local env file if exists)

Suggested `config/llm.env.example`:
- `QWEN_PROVIDER=stub`
- `QWEN_BASE_URL=`
- `QWEN_API_KEY=`
- `QWEN_MODEL=qwen2.5-7b-instruct`

Verify:
- 复制模板为 `config/llm.env` 后服务可读到配置
- 不配置密钥时默认 stub 不报错

---

## [ ] Commit 06 - `feat(vector): add pgvector schema and embedding backfill scripts`

Purpose:
- 落地 “vector 优先” 的 seed 搜索能力。

Changes:
- add `feature_achievement/scripts/migrate_ask_vector.py`
- add `feature_achievement/scripts/build_enriched_embeddings.py`

Run:
- `python -m feature_achievement.scripts.migrate_ask_vector`
- `python -m feature_achievement.scripts.build_enriched_embeddings`

Verify:
- `enriched_chapter_embedding` 有数据
- `$env:PYTHONPATH='.'; pytest -q`

---

## [ ] Commit 07 - `feat(retrieval): enable vector-first seed search with ilike fallback`

Purpose:
- 实现 `seed_search=auto|vector|ilike`，默认 auto。

Changes:
- update `feature_achievement/db/ask_queries.py` (vector search query)
- add `feature_achievement/ask/vector_embedder.py`
- update `feature_achievement/ask/cluster_builder.py` (auto fallback logic)
- update `feature_achievement/api/schemas/ask.py` (seed_search enum)

Verify:
- `seed_search=vector` 在无向量数据时可明确报错或回退策略符合设计
- `seed_search=auto` 可在向量不可用时自动走 ilike
- `$env:PYTHONPATH='.'; pytest -q`

---

## [ ] Commit 08 - `feat(frontend): add /ask chat panel (term + chapter ask)`

Purpose:
- 前端对话框接入，支持两类提问。

Changes:
- update `frontend/app.js` (chat state + askByTerm + askByChapter)
- update `frontend/index.html` (chat panel styles/layout)
- optional: update `frontend/graph-core/types.ts` if needed for selected chapter state

Verify:
- `npm run build:core` 通过
- 页面可输入 term 提问并显示回答
- 可对选中 chapter 发起 chapter 问题

---

## [ ] Commit 09 - `test(ask): add ask API/cluster/llm tests`

Purpose:
- 防止回归，确保 MVP 可持续迭代。

Changes:
- add `tests/test_ask_request.py`
- add `tests/test_ask_cluster_builder.py`
- add `tests/test_ask_api.py`
- add `tests/test_qwen_prompts.py`

Verify:
- `$env:PYTHONPATH='.'; pytest -q`
- 覆盖 404/409/422、term/chapter、llm stub 分支

---

## [ ] Commit 10 - `docs(ask): update README and mark ask-plan phases completed`

Purpose:
- 完成交付文档闭环。

Changes:
- update `README.md` (`/ask` usage + config + smoke examples)
- update `ask-plan.md` (每个 phase 标记 completed)
- add `feature_achievement/scripts/smoke_ask.py`

Verify:
- README 示例可直接跑通
- `python -m feature_achievement.scripts.smoke_ask`

---

## Continuous Checks (each commit)

- Backend tests: `$env:PYTHONPATH='.'; pytest -q`
- Frontend build: `npm run build:core`
- API manual smoke:
  - `POST /ask` term
  - `POST /ask` chapter
