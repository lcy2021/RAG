# RAG Lab

[中文](#中文) · [English](#english) · [Custom plugins](docs/design/custom-plugins.md) · [Architecture](docs/design.md)

---

## 中文

<a id="中文"></a>

受 [DeepSeek Harness](https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/) 插件化启发，做了这套**插件化 RAG 实验室**。

把一条 RAG 链路拆成固定阶段，每个阶段只挂一个插件；换插件 = 换配方，不用改宿主代码。页面上选插件、填参数、跑入库与对话；配方落在 PostgreSQL + pgvector。插件契约与 Harness 同构：`define` + `apply(registry)` + JSON Schema + 注入式 `ctx`。

### 为什么是可插拔 RAG

常见 RAG 把切块、向量化、召回、生成写死在一套流程里。换切块策略或加一路 BM25，往往要改核心代码。

RAG Lab 把链路拆成**可插拔阶段**：宿主只负责按槽位调度；每个阶段的实现是独立插件，可替换、可并存（检索槽支持多路 `ensemble` 再融合）。

```
入库:  loader  →  chunker  →  embedder  →  indexer
查询:  query_transformer  →  retriever(s)  →  fusion  →  reranker  →  grader  →  compressor  →  generator
```

| 你想改的 | 做法 |
| --- | --- |
| 换切块 | 槽位选 `recursive` / `semantic` / `parent_child` / `heading` |
| 混合召回 | 检索槽 `ensemble`：`dense` + `bm25`，再接 `rrf` |
| 换生成模型 | Settings 里换 LLM 凭证；生成插件只拿 `binding_id` |
| 加自己的 HyDE | 写一个 `query_transformer` 插件，`apply(registry)` 注册 |

插件通过 `binding_id` 使用凭证：`ctx` 解析后经 **LiteLLM** 调用模型；traces 记录阶段与输出。

### 插件契约（和 Harness 同构）

| DeepSeek Harness | RAG Lab |
| --- | --- |
| `defineTool` | `define_stage` |
| `apply` / `register` | `apply(registry)` → `registry.register` |
| Tool JSON Schema | `config_schema` + `default_params` |
| 注入 `ctx` | `PluginContext`（`embed_texts` / `chat_complete` / `trace`） |

一次 `define_stage` = 一个阶段的一种实现。流水线槽位选用它；参数：`default_params` ← 槽位 params；表单由 `config_schema` 生成。

```python
from plugins import define_stage

plugin = define_stage(
    stage="query_transformer",
    name="my_hyde",
    version="1.0.0",
    description="用假设答案向量检索，缩小问句与文档文体差。",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"n_hypothetical": {"type": "integer"}},
    },
    default_params={"n_hypothetical": 1},
)


@plugin.run
async def run(data, params, ctx):
    # Use ctx.embed_texts / ctx.chat_complete with binding_id
    return data


def apply(registry):
    registry.register(plugin)
```

内置插件同一套 API。自定义：在 `backend/src/plugins/custom/` 直接改代码，进程启动时加载并写入插件目录表；无上传入口。

#### 内置插件目录

| 阶段 | 可插拔实现 |
| --- | --- |
| loader | `auto`（默认；按类型路由 text / markup / layout / table / ocr）；亦可单独选 `text`、`markup`、`layout`、`table`、`ocr` |
| chunker | `recursive`, `semantic`, `parent_child`, `heading` |
| embedder | `openai_embedder`, `local_embedder` |
| indexer | `pgvector` |
| query_transformer | `passthrough`, `rewrite`, `hyde`, `multi_query` |
| retriever | `dense`, `bm25` |
| fusion | `rrf` |
| reranker | `none`, `bge-reranker` |
| grader | `crag` |
| compressor | `none`, `top_n` |
| generator | `chat` |
| evaluator | `recall_at_k`, `mrr`, `faithfulness` |

### 页面怎么配一条可插拔流水线

1. **设置** — 登记向量 / LLM 凭证（密钥入库；列表显示 `key_hint`）。
2. **插件中心** — 浏览各阶段实现（`description` + schema 字段）。
3. **流水线** — 入库 / 查询槽位图：每阶段选插件、填参数；检索可多路 ensemble。
4. **知识库** — 建库、上传文档（文本 / Office / PDF / 图片）；默认 `auto` loader 按策略抽正文后 ingest 进 pgvector；可删除单篇文档或整个知识库（软删后列表立即更新，向量与文件后台清理；对话历史保留）。
5. **场景** — 绑定知识库；选评测指标（`recall_at_k` / `mrr` / `faithfulness`）；添加评测题与文档原文依据（字符 span）。
6. **实验** — 绑定场景与至少两条已有查询流水线；后台排队离线跑评；按加权指标排序；可**晋级**胜出流水线为知识库默认。
7. **对话** — 默认选中第一个知识库与第一条查询流水线；多轮问答（SSE：`progress` 阶段进度 + 流式回答）；进度区可展开查看各阶段完整结果（改写句、段落正文与分数）；每条助手回答底部展示最终引用来源。

换插件即换配方，同一套页面与存储。自定义插件：在 `backend/src/plugins/custom/` 直接改代码。

### 技术栈

PostgreSQL 16 + pgvector · FastAPI + SQLAlchemy 2 + Alembic · LiteLLM · React 19 + Vite + Ant Design

### 快速启动

```bash
docker compose up --build
```

| | |
| --- | --- |
| 控制台 | http://localhost:6650 |
| OpenAPI | http://127.0.0.1:6660/api/v1/docs |

启动时若目标库不存在会先 `CREATE DATABASE`，再跑 Alembic，并注册全部插件。

`docker compose down` 停止。

### 本地开发

```bash
docker compose up -d postgres

cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn main:app --reload --app-dir src --port 6660

cd frontend
npm install && npm run dev
```

UI http://localhost:6650（`/api` 代理到 6660）。环境变量见 `backend/.env.example`。

```bash
cd backend && ruff check src tests && pytest
cd frontend && npm run lint && npm test
```

### 目录

```
frontend/                 槽位编辑、插件目录、入库、对话
backend/src/
  plugins/                define_stage、registry、builtin、custom（自定义插件目录）
  engine/                 按槽位跑插件、ensemble、RRF
  api/ services/ ...
  main.py
docker-compose.yml
docs/design/custom-plugins.md
```

### 贡献 / 开发

- Commit 遵循 Conventional Commits（`feat`、`fix`、`docs` 等）。
- 后端：`ruff` + `pytest`；前端：`npm run lint` + `npm test`。
- 自定义插件见 [docs/design/custom-plugins.md](docs/design/custom-plugins.md)。
- 架构说明见 [docs/design.md](docs/design.md)。

### License

[MIT](LICENSE) © 2026 Chunyu Liu

---

## English

<a id="english"></a>

[中文](#中文) · [English](#english) · [Custom plugins](docs/design/custom-plugins.md) · [Architecture](docs/design.md)

Inspired by [DeepSeek Harness](https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/) plugins, this is a **pluggable RAG laboratory**.

A RAG pipeline is split into fixed stages; each stage mounts one plugin. Swap the plugin to change the recipe—no host rewrite. In the console you pick plugins, fill params, run ingest and chat; recipes live in PostgreSQL + pgvector. The plugin contract mirrors Harness: `define` + `apply(registry)` + JSON Schema + injected `ctx`.

### Why pluggable RAG

Typical RAG hard-codes chunking, embedding, retrieval, and generation in one flow. Changing chunk strategy or adding BM25 often means editing core code.

RAG Lab splits the chain into **pluggable stages**: the host only schedules by slot; each stage implementation is an independent plugin—replaceable, and for retrieval, combinable (`ensemble` then fusion).

```
ingest:  loader  →  chunker  →  embedder  →  indexer
query:   query_transformer  →  retriever(s)  →  fusion  →  reranker  →  grader  →  compressor  →  generator
```

| You want to change | How |
| --- | --- |
| Chunking | Slot → `recursive` / `semantic` / `parent_child` / `heading` |
| Hybrid recall | Retriever `ensemble`: `dense` + `bm25`, then `rrf` |
| Generation model | New LLM credential in Settings; generator only gets `binding_id` |
| Custom HyDE | One `query_transformer` plugin + `apply(registry)` |

Plugins use credentials via `binding_id`: `ctx` resolves them and calls models through **LiteLLM**; traces record stages and outputs.

### Plugin contract (Harness-aligned)

| DeepSeek Harness | RAG Lab |
| --- | --- |
| `defineTool` | `define_stage` |
| `apply` / `register` | `apply(registry)` → `registry.register` |
| Tool JSON Schema | `config_schema` + `default_params` |
| Injected `ctx` | `PluginContext` (`embed_texts` / `chat_complete` / `trace`) |

One `define_stage` = one implementation of one stage. Pipeline slots select it; params: `default_params` ← slot params; forms are generated from `config_schema`.

```python
from plugins import define_stage

plugin = define_stage(
    stage="query_transformer",
    name="my_hyde",
    version="1.0.0",
    description="Retrieve with hypothetical-answer embeddings to close the query–doc style gap.",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {"n_hypothetical": {"type": "integer"}},
    },
    default_params={"n_hypothetical": 1},
)


@plugin.run
async def run(data, params, ctx):
    # Use ctx.embed_texts / ctx.chat_complete with binding_id
    return data


def apply(registry):
    registry.register(plugin)
```

Builtins use the same API. Custom: edit `backend/src/plugins/custom/` in place; loaded at process start into the plugin catalog. No upload UI.

#### Builtin catalog

| Stage | Pluggable implementations |
| --- | --- |
| loader | `auto` (default; routes by type to text / markup / layout / table / ocr); or `text`, `markup`, `layout`, `table`, `ocr` alone |
| chunker | `recursive`, `semantic`, `parent_child`, `heading` |
| embedder | `openai_embedder`, `local_embedder` |
| indexer | `pgvector` |
| query_transformer | `passthrough`, `rewrite`, `hyde`, `multi_query` |
| retriever | `dense`, `bm25` |
| fusion | `rrf` |
| reranker | `none`, `bge-reranker` |
| grader | `crag` |
| compressor | `none`, `top_n` |
| generator | `chat` |
| evaluator | `recall_at_k`, `mrr`, `faithfulness` |

### Console: configure a pluggable pipeline

1. **Settings** — Register embedding / LLM credentials (secrets stored; list shows `key_hint`).
2. **Plugins** — Browse implementations per stage (`description` + schema fields).
3. **Pipelines** — Ingest / query slot map: pick plugin and params per stage; retrieval supports multi-path ensemble.
4. **Knowledge bases** — Create KB, upload docs (text / Office / PDF / images); default `auto` loader extracts text then ingests to pgvector; delete single docs or whole KBs (soft-hide updates the list immediately; vectors/files cleaned in background; chat history is kept).
5. **Scenarios** — Bind a KB; pick metrics (`recall_at_k` / `mrr` / `faithfulness`); add gold questions and document evidence quotes (char spans).
6. **Experiments** — Bind a scenario to two or more existing query pipelines; queue **one offline eval job per pipeline** (parallel, with per-pipeline progress); rank by weighted metrics; **promote** the winner as the KB default query pipeline.
7. **Chat** — Defaults to first KB and first query pipeline; multi-turn Q&A (SSE: `progress` + streamed answer); expand progress for full stage outputs; citations under each assistant reply.

Swap plugins to swap recipes—same UI and storage. Custom plugins: edit `backend/src/plugins/custom/` in place.

### Tech stack

PostgreSQL 16 + pgvector · FastAPI + SQLAlchemy 2 + Alembic · LiteLLM · React 19 + Vite + Ant Design

### Quick start

```bash
docker compose up --build
```

| | |
| --- | --- |
| Console | http://localhost:6650 |
| OpenAPI | http://127.0.0.1:6660/api/v1/docs |

On startup, if the target DB is missing it runs `CREATE DATABASE`, then Alembic, then registers all plugins.

`docker compose down` to stop.

### Local development

```bash
docker compose up -d postgres

cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
uvicorn main:app --reload --app-dir src --port 6660

cd frontend
npm install && npm run dev
```

UI http://localhost:6650 (`/api` proxies to 6660). Env vars: `backend/.env.example`.

```bash
cd backend && ruff check src tests && pytest
cd frontend && npm run lint && npm test
```

### Project structure

```
frontend/                 Slot editor, plugin catalog, ingest, chat
backend/src/
  plugins/                define_stage, registry, builtin, custom (drop-in plugins)
  engine/                 Slot runner, ensemble, RRF
  api/ services/ ...
  main.py
docker-compose.yml
docs/design/custom-plugins.md
```

### Contribution / development

- Follow Conventional Commits (`feat`, `fix`, `docs`, …).
- Backend: `ruff` + `pytest`; frontend: `npm run lint` + `npm test`.
- Custom plugins: see [docs/design/custom-plugins.md](docs/design/custom-plugins.md).
- Architecture notes: [docs/design.md](docs/design.md).

### License

[MIT](LICENSE) © 2026 Chunyu Liu
