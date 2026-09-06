# RAG Lab 架构 / Architecture

> **中文** ↓ · **[English](#english)**  
> Schema: ORM + Alembic (`backend/src/db/entities.py`, `backend/src/alembic/`) 
> Notes: [UI](design/ui.md) · [DB](design/database.md) · [Backend](design/backend.md) · [Config](design/configuration.md) · [Compare](design/compare-eval.md) · [Params](design/plugin-params.md) · [Plugins](design/custom-plugins.md)

---

## 中文

产品是 **Web 实验室**。凭证、流水线、知识库、对比矩阵、评测与对话都在页面上完成，写入 **PostgreSQL + pgvector**（稠密向量存在 `chunk_embeddings`）。[`lab.yml`](../lab.yml) 用于导入/导出示例。

### 目标

在给定场景（这批文档 + 这类题 + 指标/时延成本）下，替换各环节插件并评出最优配方，再晋级为知识库默认。

能力：ingest + query 全链路插件；显式选定的流水线变体；查询侧换件；入库侧换 collection 后对比；多轮对话；带参考答案与原文依据的评测题；并排 traces；晋级。

### 页面即配置（主路径）

| 页面 | 操作 |
|---|---|
| 设置 / 密钥 | 登记向量或 LLM 凭证；密钥入库（列表显示 key_hint） |
| 插件 | 浏览内置目录；自定义 `.py` 经 `RAGLAB_CUSTOM_PLUGIN_DIR` 注册（表单由 `config_schema` 生成） |
| 流水线 | 可视化槽位：每环节选插件、填 params |
| 知识库 | 建库、上传文档、看 ingest 任务、管理向量 collection |
| 场景 | 评测题（问题、参考答案、原文依据）、指标与权重、SLO |
| 对比实验 | 选场景；多选已有查询流水线对比；运行；分数表；晋级 |
| 对话 | 多轮问答；可选同一对比计划并排 traces |

表单字段来自插件 JSON Schema；插件通过 `binding_id` 引用凭证。导出/导入 YAML 映射为同一套 API。

### 插件与参数

每阶段一个插件。`config_schema` + `default_params`。合并：默认 ← 流水线绑定 ← 变体覆盖。结果写入 `rag_runs.resolved_params`。

### 场景与评测

场景 = 知识库 + 评测题集 + 指标。每道评测题包含问题、参考答案，以及文档里标出的**原文依据**（字符 span）。`eval_experiments` 绑定 `scenario` + `compare_spec`。跑完汇总 `eval_summaries`，可 promote。

### 实现顺序

M1 页面骨架（设置、入库、Naive 对话，`frontend/`）→ M2 Hybrid → M3 对比/评测页 → M4 入库变体 → M5 晋级。

---

## English

<a id="english"></a>

The product is a **web lab**. Credentials, pipelines, knowledge bases, compare matrices, eval, and chat are completed **in the UI** and persisted in **PostgreSQL + pgvector** (`chunk_embeddings`). [`lab.yml`](../lab.yml) supports import/export examples.

### Goals

Swap stage plugins for a **scenario** (this corpus + this question mix + SLOs), score quality/latency/cost, and **promote** the winner as the KB default.

Capabilities: full ingest + query plugins; explicit pipeline variants; query-side swaps; ingest-side swaps via new collections; multi-turn chat; span labels; traces; promote.

### UI is the config surface

| Page | What you do |
|---|---|
| Settings / credentials | Vector or LLM credential (list shows key hint) |
| Plugins | Builtin catalog; custom `.py` via `RAGLAB_CUSTOM_PLUGIN_DIR`; param forms from `config_schema` |
| Pipelines | Visual slots: pick plugin + params per stage |
| Knowledge bases | Create, upload docs, ingest jobs, vector collections |
| Scenarios | Gold questions + document evidence spans, metrics, weights, SLOs |
| Compare lab | Pick scenario; select multiple existing query pipelines; run; score table; promote |
| Chat | Multi-turn; optional side-by-side traces for the same compare spec |

JSON Schema drives forms; plugins reference credentials with `binding_id`. YAML import/export maps to the same APIs.

### Plugins and params

One plugin per stage. Merge: `default_params` ← pipeline bindings ← variant overrides. Store `rag_runs.resolved_params`.

### Scenario and eval

A scenario is KB + gold set + metrics. Labels are document character spans. `eval_experiments` bind scenario + compare spec. Summaries then optional promote.

### Build order

M1 UI shell (settings, ingest, naive chat in `frontend/`) → M2 hybrid → M3 compare/eval pages → M4 ingest variants → M5 promote.
