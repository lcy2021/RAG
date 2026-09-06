# Database / 数据库

> **中文** ↓ · **[English](#english)**  
> ORM: `backend/src/db/entities.py` · 迁移: `backend/src/alembic/` · [架构](../design.md)

---

## 中文

PostgreSQL（含 **pgvector**）同时存业务数据和稠密向量。页面上的每次保存都落到这些表。对比不同 embedding 使用不同的 `vector_collections` 行（`chunk_embeddings` 按 collection 过滤；dim 必须一致）。

**迁移（类似 EF Core）：** 改 `entities.py` → `cd backend && alembic revision --autogenerate -m "reason"`。进程启动（`database_enabled`）会自动 `upgrade head`；也可手动 `raglab-migrate`。已有表、缺少 `alembic_version` 的库应 `alembic stamp head`。

域：凭证（向量/LLM）→ 知识库/文档/切块 → **chunk_embeddings** → 流水线与插件目录（含 `description`） → 对比 spec/变体 → 场景与评测题（原文依据） → 对话 → 运行 traces → 评测分数/汇总 → 晋级。

`rag_runs`：在线对话（`conversation_id`）或离线评测（`eval_run_id` + `eval_item_id`）。原文依据存在 `eval_item_spans`（文档字符 span）。

已移除未接线表（`0005`）：`conversation_memories`、`message_embeddings`、`sparse_index_refs`、`compare_groups`（及 `rag_runs.compare_group_id`）。

---

## English

<a id="english"></a>

PostgreSQL with **pgvector** stores both app data and dense vectors. Every UI save lands in these tables. Comparing embedders uses separate `vector_collections` rows (`chunk_embeddings` filtered by collection; dim must match).

**Migrations (EF Core analogue):** edit mapped models → `alembic revision --autogenerate -m "reason"`. API boot applies `upgrade head` when the database is enabled; `raglab-migrate` does the same. Databases that already have tables but no `alembic_version` should `alembic stamp head`.

Domains: credentials (vector/LLM) → KB/docs/chunks → **chunk_embeddings** → pipelines/plugin catalog → compare spec/variants → scenarios/span gold → chat → traces → eval scores/summaries → promotions.

A `rag_run` is either online (`conversation_id`) or eval (`eval_run_id` + `eval_item_id`). Gold labels are `eval_item_spans` (document character spans).

Removed unused reserved tables (`0005`): `conversation_memories`, `message_embeddings`, `sparse_index_refs`, `compare_groups` (and `rag_runs.compare_group_id`).
