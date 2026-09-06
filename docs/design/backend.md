# Backend / 后端

> **中文** ↓ · **[English](#english)** · [架构](../design.md)

Code lives under `backend/src/` (`api`, `services`, `plugins`, …).

---

## 中文

分层：`api` → `services` → `repositories`（SQLAlchemy 2 ORM）→ PostgreSQL。Schema 由 **Alembic** 管理（`raglab-migrate` / 启动时 `upgrade head`）。

**启动：** 把 builtin（以及 `RAGLAB_CUSTOM_PLUGIN_DIR` 下的 `.py`）登记进内存注册表，再 **upsert** 到 `plugins` 表（`ON CONFLICT (stage, name, version)`）。`GET /api/v1/plugins` 在数据库可用时读该表。

**Pipeline 运行时：** 从 `pipeline_slots` 按 ingest/query 固定阶段顺序执行。`mode=first` 取第一个 binding；检索槽 `mode=ensemble` 时并行跑多个 retriever，再交给 `rrf`。参数 `default_params ← bindings.params`（评测时再叠 `slot_overrides`）。`ctx` 提供 binding 解析、embedding/chat（经 **LiteLLM**）、KB 仓储与 traces。

**对话流式：** `POST /conversations/{id}/messages/stream` 返回 SSE。事件顺序：`meta`（user + rag_run_id）→ `delta`（生成 token）→ `done`（完整 turn + traces）或 `error`。`generator.chat` 在 `ctx.extra.on_token` 存在时走 `chat_stream`；非流式 `POST .../messages` 可用。删除会话：`DELETE /conversations/{id}`（级联清理消息与 rag runs）。

内置插件（对照 [小林 RAG 专题](https://www.xiaolinnote.com/ai/rag/rag_info.html)）：切块 `recursive` / `semantic` / `parent_child` / `heading`；查询 `passthrough` / `rewrite` / `hyde` / `multi_query`；召回 `dense` + `bm25`（`mode=ensemble`）+ `rrf`；精排 `none` / `bge-reranker`；纠错 `crag`；指标 `recall_at_k` / `mrr` / `faithfulness`。

凭证：粘贴后以 UTF-8 写入 `credentials`；类型为 `vector` 或 `llm`。界面显示 `key_hint`。插件参数里的 `binding_id` 指向该行。

---

## English

<a id="english"></a>

On boot the process applies Alembic migrations, registers builtin (+ custom `.py`) in memory, then upserts `plugins`. Repositories use SQLAlchemy mapped entities. Runtime pipelines walk slots in stage order (`ensemble` retrievers run in parallel then `rrf`). Plugins follow [Xiaolin RAG notes](https://www.xiaolinnote.com/ai/rag/rag_info.html): heading/semantic/parent-child chunking, rewrite/HyDE/multi-query, dense+BM25, rerank, CRAG.

Secrets are stored as UTF-8 bytes in `credentials`. Kinds are `vector` | `llm`. UI shows `key_hint`; plugins resolve keys via `binding_id`. Chat/embed go through **LiteLLM** (`LiteLLMClient`) so OpenAI-compatible bases (Azure `/openai/v1`, Ollama, vLLM) share one path. Chat UI uses SSE (`POST .../messages/stream`: `meta` → `delta*` → `done`|`error`); the non-stream `POST .../messages` endpoint remains for simple clients.
