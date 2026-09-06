# RAG Lab 架构 / Architecture

> **中文** ↓ · **[English](#english)**  
> Schema: ORM + Alembic (`backend/src/db/entities.py`, `backend/src/alembic/`) 
> Notes: [UI](design/ui.md) · [DB](design/database.md) · [Backend](design/backend.md) · [Config](design/configuration.md) · [Compare](design/compare-eval.md) · [Params](design/plugin-params.md) · [Plugins](design/custom-plugins.md)

---

## 中文

产品是 **Web 实验室**。密钥、流水线、知识库、对比矩阵、评测与对话都在页面上完成，写入 **PostgreSQL + pgvector**（稠密向量存在 `chunk_embeddings`）。[`lab.yml`](../lab.yml) 只是 **导入/导出示例**，不是日常启动方式。

### 目标

在给定场景（这批文档 + 这类题 + 指标/时延成本）下，替换各环节插件并评出最优配方，再晋级为知识库默认。

范围内：ingest + query 全链路插件；显式变体（不自动笛卡尔积）；查询侧换件；入库侧换 collection 后对比；多轮对话；带参考答案与原文依据的评测题；并排 traces；晋级。

暂不做：全组合自动搜索、GraphRAG 表、账号体系。

### 页面即配置（主路径）

| 页面 | 操作 |
|---|---|
| 设置 / 密钥 | 登记向量或 LLM 凭证；密钥入库（列表只显示 key_hint） |
| 插件 | 浏览内置目录；上传自定义 `.py` 注册（表单由 `config_schema` 生成） |
| 流水线 | 可视化槽位：每环节选插件、填 params |
| 知识库 | 建库、上传文档、看 ingest 任务、管理向量 collection |
| 场景 | 评测题（问题、参考答案、原文依据）、指标与权重、SLO |
| 对比实验 | 选场景；多选已有查询流水线对比；运行；分数表；晋级 |
| 对话 | 多轮问答；可选同一对比计划并排 traces |

表单字段来自插件 JSON Schema，禁止出现 `api_key`。导出/导入 YAML 是高级功能，映射为同一套 API。

### 插件与参数

每阶段一个插件。`config_schema` + `default_params`。合并：默认 ← 流水线绑定 ← 变体覆盖。结果写入 `rag_runs.resolved_params`。

### 场景与评测

场景 = 知识库 + 评测题集 + 指标。每道评测题包含问题、参考答案，以及文档里标出的**原文依据**（不是切块 ID）。`eval_experiments` 绑定 `scenario` + `compare_spec`。跑完汇总 `eval_summaries`，可 promote。

### 实现顺序

M1 页面骨架（设置、入库、Naive 对话，`frontend/`）→ M2 Hybrid → M3 对比/评测页 → M4 入库变体 → M5 晋级 → 后续 CRAG / Graph。

---

## English

<a id="english"></a>

The product is a **web lab**. Credentials, pipelines, knowledge bases, compare matrices, eval, and chat are completed **in the UI** and persisted in **PostgreSQL + pgvector** (`chunk_embeddings`). [`lab.yml`](../lab.yml) is an **import/export example**, not the daily boot path.

### Goals

Swap stage plugins for a **scenario** (this corpus + this question mix + SLOs), score quality/latency/cost, and **promote** the winner as the KB default.

In scope: full ingest + query plugins; explicit variants (no auto Cartesian grid); query-side swaps; ingest-side swaps via new collections; multi-turn chat; span labels; traces; promote.

Out of scope for now: auto grid search, GraphRAG tables, user accounts.

### UI is the config surface

| Page | What you do |
|---|---|
| Settings / credentials | Vector or LLM credential (list shows key hint only) |
| Plugins | Builtin catalog; upload a custom `.py`; param forms from `config_schema` |
| Pipelines | Visual slots: pick plugin + params per stage |
| Knowledge bases | Create, upload docs, ingest jobs, vector collections |
| Scenarios | Gold questions + document evidence spans, metrics, weights, SLOs |
| Compare lab | Pick scenario; select multiple existing query pipelines; run; score table; promote |
| Chat | Multi-turn; optional side-by-side traces for the same compare spec |

JSON Schema drives forms. No `api_key` fields. YAML import/export is an advanced shortcut over the same APIs.

### Plugins and params

One plugin per stage. Merge: `default_params` ← pipeline bindings ← variant overrides. Store `rag_runs.resolved_params`.

### Scenario and eval

A scenario is KB + gold set + metrics. Labels are document spans, not chunk UUIDs. `eval_experiments` bind scenario + compare spec. Summaries then optional promote.

### Build order

M1 UI shell (settings, ingest, naive chat in `frontend/`) → M2 hybrid → M3 compare/eval pages → M4 ingest variants → M5 promote → later CRAG / Graph.
