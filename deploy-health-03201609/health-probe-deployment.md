# `/healthz` 与 `/readyz` 部署说明

## 1. 这两个地址是什么

- `GET /healthz`
  - 用途：最小存活检查。
  - 含义：只要 FastAPI 进程还活着，就返回 `200 {"status":"ok"}`。
  - 适合：负载均衡器基础探针、容器存活探针、最小外部连通检查。

- `GET /readyz`
  - 用途：最小就绪检查。
  - 含义：除了 API 进程存活，还会执行一次数据库连通检查；成功返回 `200 {"status":"ready"}`，失败返回 `503 {"detail":"database not ready"}`。
  - 适合：平台启动就绪探针、发布后切流前检查。

## 2. 已经做了什么

### 2.1 配置化已完成

- `DATABASE_URL` 已配置化。
- `CORS_ORIGINS` 已配置化。
- 已新增 `config/app.env.example` 作为示例。
- 已新增 `requirements.txt`，便于服务端安装 Python 依赖。

### 2.2 健康检查接口已完成

- 已新增路由文件：
  - `feature_achievement/api/routers/health.py`
- 已在应用入口挂载：
  - `feature_achievement/api/main.py`
- 已提供两个接口：
  - `GET /healthz`
  - `GET /readyz`

### 2.3 测试已完成

- 已新增接口测试：
  - `tests/test_health_api.py`
- 已验证：
  - `/healthz` 正常返回 200
  - `/readyz` 在数据库可用时返回 200
  - `/readyz` 在数据库不可用时返回 503

## 3. 接下来围绕这两个地址还可以做什么

### 3.1 立刻可做：把它们接入部署探针

这是最直接的一步。

- 用 `/healthz` 做存活探针
  - 目标：判断服务进程是否还活着。
- 用 `/readyz` 做就绪探针
  - 目标：判断服务是否已经能连上数据库并接流量。

这样做的价值：

- 服务假死时，平台能更快发现。
- 数据库不可用时，平台不会过早把流量打进来。
- 后续扩容、重启、滚动发布更稳。

### 3.2 部署后可做：把它们接入监控

- 定时从外部监控系统请求：
  - `https://your-api.example.com/healthz`
  - `https://your-api.example.com/readyz`
- 记录状态码、响应时延、失败次数。
- 当 `/readyz` 连续失败时报警。

### 3.3 再下一步可做：区分更细的健康维度

如果之后你觉得需要更强的可观测性，可以继续扩展：

- `/healthz`
  - 继续保持极简，不查数据库。
- `/readyz`
  - 继续只查最关键依赖，例如数据库。
- 可选新增 `/health/details`
  - 返回更细的子项状态，例如数据库、LLM provider、磁盘、关键配置是否存在。

当前阶段不建议把所有依赖都塞进 `/healthz`，否则会把“进程是否活着”和“依赖是否全部可用”混在一起。

## 4. 具体怎么做

### 4.1 服务器启动后手工检查

服务启动后直接请求：

```bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
```

预期：

```json
{"status":"ok"}
```

```json
{"status":"ready"}
```

如果 `/healthz` 成功而 `/readyz` 失败，通常说明：

- API 进程已启动
- 但数据库配置不对，或数据库暂时不可达

需要重点检查：

- `config/app.env`
- `DATABASE_URL`
- 数据库用户权限
- 服务器到数据库的网络连通性

### 4.2 反向代理或网关层检查

如果你后面用 Nginx、云负载均衡、平台健康探针，直接把探针地址指向：

- liveness: `/healthz`
- readiness: `/readyz`

原则：

- 不要用 `/ask` 做健康检查。
- 不要用 `/graph` 做健康检查。
- 不要让探针依赖大查询或复杂业务流程。

原因很简单：

- 健康检查应该快、稳、低成本。
- `/ask` 是业务接口，依赖数据库、数据状态、甚至 LLM 配置，不适合拿来做平台探针。

### 4.3 Docker 场景怎么接

如果后面补 Dockerfile，可以在容器里把健康检查接到 `/healthz`。

示意：

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://127.0.0.1:8000/healthz || exit 1
```

如果平台支持启动后就绪探针，再额外把 readiness 指向 `/readyz`。

### 4.4 云平台场景怎么接

大部分平台都会让你填写一个或两个探针路径。

建议填写：

- Health Check Path: `/healthz`
- Readiness Path: `/readyz`

如果平台只允许填一个，优先级一般是：

1. 有独立 liveness 和 readiness 时，分别填两个
2. 只有一个探针时，优先考虑 `/readyz`

原因：

- `/readyz` 更接近“这个服务现在能不能真正接请求”

但如果你的平台会因为 readiness 抖动频繁重启容器，也可以先保守地只用 `/healthz`。

## 5. 上线前围绕这两个地址的最小检查清单

### 5.1 配置

- `config/app.env` 中 `DATABASE_URL` 已改为线上库地址
- `config/app.env` 中 `CORS_ORIGINS` 已改为线上前端域名
- `config/llm.env` 已按上线策略配置

### 5.2 服务

- `uvicorn` 已能在服务器正常启动
- `GET /healthz` 返回 200
- `GET /readyz` 返回 200

### 5.3 数据

- 线上数据库已完成表初始化
- 线上数据库已有 `/ask` 所需数据：
  - `runs`
  - `enriched_chapter`
  - `edges`

## 6. 现在最建议的下一步

如果目标是尽快上线一个稳定版本，推荐按这个顺序推进：

1. 先准备线上 PostgreSQL。
2. 把当前本地可用的数据迁移到线上，或者在线上重建数据。
3. 启动后端服务。
4. 先用 `curl` 检查 `/healthz` 和 `/readyz`。
5. 再部署前端并接入线上 API。
6. 最后把平台探针正式指向这两个地址。

## 7. 当前结论

围绕这两个地址，最核心的工作已经完成：

- 探针接口已存在
- 基本语义已经分清
- 测试已经补上

接下来真正要做的，不再是继续写这两个接口本身，而是：

- 把它们接到你的部署平台
- 用它们验证线上数据库和 API 的实际就绪状态
- 让上线过程具备最基本的可观测性和回滚判断依据
