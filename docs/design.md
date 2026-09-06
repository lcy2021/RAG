# RAG Lab 架构 / Architecture

> **中文** ↓ · **[English](#english)**  
> Schema: ORM + Alembic (`backend/src/db/entities.py`, `backend/src/alembic/`)  
> Notes: [UI](design/ui.md) · [DB](design/database.md) · [Backend](design/backend.md) · [Config](design/configuration.md) · [Compare](design/compare-eval.md) · [Params](design/plugin-params.md) · [Plugins](design/custom-plugins.md)

---

## 中文

RAG Lab 是浏览器里操作的插件化 RAG 实验台：凭证、流水线、知识库、对比评测与对话都在页面上完成，写入 **PostgreSQL + pgvector**（稠密向量在 `chunk_embeddings`）。配置以 UI + API 为准；自定义插件经 `RAGLAB_CUSTOM_PLUGIN_DIR` 加载。

### 目标

在给定场景（这批文档 + 这类题 + 指标/时延成本）下，替换各环节插件并评出最优配方，再晋级为知识库默认。

能力：ingest + query 全链路插件；多条完整查询流水线对比；查询侧换件；入库侧换 collection 后对比；多轮对话（SSE + 阶段时间线）；带参考答案与原文依据的评测题；实验 traces；晋级。

### 页面即配置（主路径）

| 页面 | 操作 |
|---|---|
| 设置 / 密钥 | 登记向量或 LLM 凭证；密钥入库（列表显示 key_hint） |
| 插件 | 浏览内置目录；自定义 `.py` 经 `RAGLAB_CUSTOM_PLUGIN_DIR` 注册（表单由 `config_schema` 生成） |
| 流水线 | 可视化槽位：每环节选插件、填 params；检索槽可 `ensemble` |
| 知识库 | 建库、上传文档、看 ingest 任务、管理向量 collection |
| 场景 | 评测题（问题、参考答案、原文依据）、指标与权重 |
| 对比实验 | 选场景；多选已有查询流水线；并行跑评；分数表；晋级 |
| 对话 | 选知识库与查询流水线；多轮问答；助手气泡内展开阶段结果与 Sources |

表单字段来自插件 JSON Schema；插件通过 `binding_id` 引用凭证。

### 插件与参数

每阶段一个插件（检索槽可为多路 ensemble）。`config_schema` + `default_params`。合并：默认 ← 流水线绑定 ←（评测时可选）变体 `slot_overrides`。结果写入 `rag_runs.resolved_params`。对比的主轴是**整条查询流水线**，不是页面上的 YAML 配方。

### 场景与评测

场景 = 知识库 + 评测题集 + 指标。每道评测题包含问题、参考答案，以及文档里标出的**原文依据**（字符 span）。`eval_experiments` 绑定 `scenario` + `compare_spec`。跑完汇总 `eval_summaries`，可 promote。

### 实现状态

设置 / 插件 / 流水线 / 知识库 / 场景 / 实验（多流水线并行评测 + 晋级）/ 对话（SSE）已落地。入库侧换 embedding/切块通过新建 collection 再 ingest。

---

## English

<a id="english"></a>

RAG Lab is a browser-based, pluggable RAG workbench: credentials, pipelines, knowledge bases, compare/eval, and chat are done in the UI and stored in **PostgreSQL + pgvector** (`chunk_embeddings`). The UI + APIs are the source of truth; custom plugins load from `RAGLAB_CUSTOM_PLUGIN_DIR`.

### Goals

Swap stage plugins for a **scenario** (this corpus + this question mix + SLOs), score quality/latency/cost, and **promote** the winner as the KB default.

Capabilities: full ingest + query plugins; compare via multiple complete query pipelines; query-side swaps; ingest-side swaps via new collections; multi-turn chat (SSE + stage timeline); span labels; experiment traces; promote.

### UI is the config surface

| Page | What you do |
|---|---|
| Settings / credentials | Vector or LLM credential (list shows key hint) |
| Plugins | Builtin catalog; custom `.py` via `RAGLAB_CUSTOM_PLUGIN_DIR`; param forms from `config_schema` |
| Pipelines | Visual slots: pick plugin + params per stage; retriever may be `ensemble` |
| Knowledge bases | Create, upload docs, ingest jobs, vector collections |
| Scenarios | Gold questions + document evidence spans, metrics, weights |
| Compare lab | Pick scenario; select multiple existing query pipelines; run; score table; promote |
| Chat | Pick KB + query pipeline; multi-turn; expand stage results and Sources on assistant turns |

JSON Schema drives forms; plugins reference credentials with `binding_id`.

### Plugins and params

One plugin per stage (retriever slot may be ensemble). Merge: `default_params` ← pipeline bindings ← optional eval `slot_overrides`. Store `rag_runs.resolved_params`. The primary compare axis is **whole query pipelines**, not a file-based recipe.

### Scenario and eval

A scenario is KB + gold set + metrics. Labels are document character spans. `eval_experiments` bind scenario + compare spec. Summaries then optional promote.

### Status

Settings / plugins / pipelines / KB / scenarios / experiments (parallel multi-pipeline eval + promote) / chat (SSE) are shipped. Ingest-side embedder/chunker swaps use a new collection and reingest.
