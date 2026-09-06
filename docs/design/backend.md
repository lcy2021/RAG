# Backend / 后端

> **中文** ↓ · **[English](#english)** · [架构](../design.md)

Code lives under `backend/src/` (`api`, `services`, `plugins`, …).

---

## 中文

分层：`api` → `services` → `repositories`（SQLAlchemy 2 ORM）→ PostgreSQL。Schema 由 **Alembic** 管理（`raglab-migrate` / 启动时 `upgrade head`）。

**启动：** 把 builtin（以及 `plugins/custom/` 下的 `.py`）登记进内存注册表，再 **upsert** 到 `plugins` 表（`ON CONFLICT (stage, name, version)`）。`GET /api/v1/plugins` 在数据库可用时读该表。

**Pipeline 运行时：** 从 `pipeline_slots` 按 ingest/query 固定阶段顺序执行。`mode=first` 取第一个 binding；检索槽 `mode=ensemble` 时并行跑多个 retriever，再交给 `rrf`。参数 `default_params ← bindings.params`（评测时再叠 `slot_overrides`）。`ctx` 提供 binding 解析、embedding/chat（经 **LiteLLM**）、KB 仓储与 traces。对话与评测中每次 chat/embed 的 token 与成本累加到 `ctx.usage`，结束时写入 `rag_runs.token_in` / `token_out` / `cost_micros`；实验汇总为 `cost_micros_avg`（并尊重场景 `cost_micros_max` SLO）。

**对话流式：** `POST /conversations/{id}/messages/stream` 返回 SSE。事件顺序：`meta`（user + rag_run_id）→ `delta`（生成 token）→ `done`（完整 turn + traces）或 `error`。`generator.chat` 在 `ctx.extra.on_token` 存在时走 `chat_stream`；非流式 `POST .../messages` 可用。删除会话：`DELETE /conversations/{id}`（级联清理消息与 rag runs）。

**用量：** `GET /usage/summary`、`/usage/conversations`、`/usage/experiments` 聚合 `rag_runs` 的 token / 成本（对话 vs 评测）。

内置插件（对照 [小林 RAG 专题](https://www.xiaolinnote.com/ai/rag/rag_info.html)）：切块 `recursive` / `semantic` / `parent_child` / `heading`；查询 `passthrough` / `rewrite` / `hyde` / `multi_query`；召回 `dense` + `bm25`（`mode=ensemble`）+ `rrf`；精排 `none` / `bge-reranker`；纠错 `crag`；指标 `recall_at_k` / `mrr` / `faithfulness`。

凭证：粘贴后经 `encode_secret` 以 **UTF-8** 写入 `credentials.encrypted_payload`（BYTEA；当前无额外 at-rest 加密）；类型为 `vector` 或 `llm`。界面显示 `key_hint`。

---

## English

<a id="english"></a>

On boot the process applies Alembic migrations, registers builtin (+ custom `.py`) in memory, then upserts `plugins`. Repositories use SQLAlchemy mapped entities. Runtime pipelines walk slots in stage order (`ensemble` retrievers run in parallel then `rrf`). Plugins follow [Xiaolin RAG notes](https://www.xiaolinnote.com/ai/rag/rag_info.html): heading/semantic/parent-child chunking, rewrite/HyDE/multi-query, dense+BM25, rerank, CRAG.

Secrets go through `encode_secret` as **UTF-8** into `credentials.encrypted_payload` (BYTEA; no extra at-rest encryption today). Kinds are `vector` | `llm`. UI shows `key_hint`. Chat/embed go through **LiteLLM** (`LiteLLMClient`) so OpenAI-compatible bases (Azure `/openai/v1`, Ollama, vLLM) share one path. Each call’s tokens/cost accumulate on `ctx.usage` and persist to `rag_runs` (`token_in` / `token_out` / `cost_micros`); eval summaries expose `cost_micros_avg` and honor scenario `cost_micros_max`. Chat UI uses SSE (`POST .../messages/stream`: `meta` → `delta*` → `done`|`error`); the non-stream `POST .../messages` endpoint remains for simple clients.
