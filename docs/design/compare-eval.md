# Compare & eval / 对比与评估

> **中文** ↓ · **[English](#english)** · [架构](../design.md) · [界面](ui.md)

---

## 中文

在 **流水线** 页先建好多条完整查询流水线，再在 **实验** 页选场景与至少两条流水线做对比（保存为 `compare_specs` + `compare_variants`）。

绑定：`eval_experiments` = `scenario_id` + `compare_spec_id`。每个变体对应一条 `query_pipeline_id`（可选手动 `slot_overrides`）。分数键：`(eval_run_id, eval_item_id, compare_variant_id, metric)`。检索指标把 span 映射到该变体的 chunk。开始评测后**各查询流水线并行**跑题；`eval_runs.snapshot` 进度写入用进程内锁串行化（`queued` → `running` → `succeeded|failed`，含 `done_items/total_items`）。全部结束后汇总 run。结果页可晋级：把胜出流水线设为知识库默认，并记录 `pipeline_promotions`。

对话页只跑**一条**选定的查询流水线（可看阶段 traces），不做多臂并排对比。实验定义在 `compare_specs` / `compare_variants` 上。

---

## English

<a id="english"></a>

Create full query pipelines on **Pipelines**, then on **Experiments** bind a scenario to at least two of them (`compare_specs` + `compare_variants`).

Bind: `eval_experiments` = `scenario_id` + `compare_spec_id`. Each variant points at a `query_pipeline_id` (optional `slot_overrides`). Score key: `(eval_run_id, eval_item_id, compare_variant_id, metric)`. Retrieval metrics map spans onto that variant’s chunks. Pipeline variants run **in parallel**; writes to `eval_runs.snapshot` progress are serialized with an in-process lock (`queued` → `running` → `succeeded|failed`, with `done_items/total_items`). The parent run finishes after all variants. Promote sets the KB default query pipeline to the winner and records `pipeline_promotions`.

Chat runs a **single** selected query pipeline (with stage traces), not multi-arm side-by-side compare. Experiment definitions live on `compare_specs` / `compare_variants`.
