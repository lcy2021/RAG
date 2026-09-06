# UI / 界面

> **中文** ↓ · **[English](#english)**  
> 主文档：[../design.md](../design.md)

---

## 中文

实验室的操作面是浏览器。API 给页面使用；`lab.yml` 对应「导入配置」对话框。

实现：`frontend/`，Vite + React + TypeScript。选用 **Ant Design**（布局、表格、表单、上传、JSON Schema 槽位）。界面文案用 **i18next**（中/英，顶栏切换，写入 `localStorage`）。开发时 Vite 代理 `/api` → FastAPI（`localhost:6660`）。

已实现：`/settings`、`/plugins`、`/pipelines`、`/kb`、`/scenarios`、`/experiments`、`/chat`。

### 信息架构

```
设置
  向量 / LLM 凭证
插件中心
  内置目录（自定义插件经 RAGLAB_CUSTOM_PLUGIN_DIR）
流水线
  入库流水线 / 查询流水线（槽位编辑器）
知识库
  列表 / 文档上传 / 任务进度 / Collection
场景
  题集 / 证据标注 / 指标权重
实验
  选择多条查询流水线对比 / 运行中 / 结果与 traces / 晋级
对话
  左侧历史会话列表；输入框内选知识库与查询流水线；助手气泡顶部流水线时间线可展开查看各阶段完整结果；底部 Sources 为最终引用
```

### 关键交互

- **槽位编辑器**：按 stage 下拉已注册插件；右侧根据 `config_schema` 渲染表单；保存为 `pipeline_slots.bindings`。
- **对比构建器**：多选已有查询流水线；每条流水线作为一个对比臂。运行后按流水线入队并展示进度，结束后跳转结果表（流水线 × 指标），点开看 traces。
- **晋级**：结果页按钮把胜出流水线设为知识库默认查询流水线，并记录 `pipeline_promotions`；对话页可再选流水线。

### 路由

| 路径 | 页面 |
|---|---|
| `/settings` | 凭证（向量 / LLM） |
| `/plugins` | 插件目录 |
| `/pipelines` | 流水线编辑 |
| `/kb` | 知识库与文档 |
| `/scenarios` | 场景与评测题 |
| `/experiments` | 对比与评测 |
| `/chat` | 多轮对话（SSE 流式回答） |

---

## English

<a id="english"></a>

The operator surface is the browser. APIs serve the UI. `lab.yml` maps to an “Import config” dialog.

Implementation: `frontend/` with Vite + React + TypeScript. **Ant Design** covers the lab console (layout, tables, forms, upload, JSON Schema slots). Copy is **i18next**-driven (zh/en, header switch, persisted in `localStorage`). Vite proxies `/api` to FastAPI on port 6660.

Shipped routes: `/settings`, `/plugins`, `/pipelines`, `/kb`, `/scenarios`, `/experiments`, `/chat`.

### Information architecture

Settings (vector/LLM credentials) → Plugin hub (builtin catalog; custom plugins via `RAGLAB_CUSTOM_PLUGIN_DIR`) → Pipelines (ingest / query slot editor) → Knowledge bases (upload, jobs, collections) → Scenarios (items, spans, weights) → Experiments (compare builder, runs, traces, promote) → Chat (composer with KB + query pipeline selectors; expandable stage timeline with full passage results; final Sources under the answer).

### Key interactions

- **Slot editor:** stage dropdown of registered plugins; JSON Schema form on the right; save as `pipeline_slots.bindings`.
- **Compare builder:** multi-select existing query pipelines; each pipeline is one compare arm. After start, each pipeline is queued with live progress; then a pipeline × metric table with drill-in traces.
- **Promote:** sets the KB default query pipeline to the winner; pick the query pipeline in Chat.

### Routes

`/settings`, `/plugins`, `/pipelines`, `/kb`, `/scenarios`, `/experiments`, `/chat`.
