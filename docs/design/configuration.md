# Configuration / 配置

> **中文** ↓ · **[English](#english)** · [架构](../design.md) · [界面](ui.md)

---

## 中文

配置在 **设置 / 流水线 / 知识库** 页面完成，不是靠启动 YAML。

- **密钥**：一种凭证，类型为向量或 LLM（**无 rerank 类型**）；粘贴的密钥入库（本地实验室不做 at-rest 加密），界面只显示 `key_hint`。插件参数用 `binding_id` 引用该行。运行时经 **LiteLLM** 调用；有自定义 `base_url` 时模型会映射为 `openai/<model>`。高级覆盖可写在凭证 `extra`：`litellm_model`、`provider`。真 Cross-Encoder（`BAAI/bge-reranker-v2-m3` 等）请 [自行开发 reranker 插件](custom-plugins.md)。
- **上传**：知识库页选择文件 → `stored_files` → `documents` → ingest。默认 loader `auto` 按策略路由（text / markup / layout / table / ocr）；流水线也可单独挂 `text`、`table`、`ocr` 等做对比。`text_file` 是 `auto` 的兼容别名。换 embedding/切块必须新建 collection 并重新入库。
- **导入 YAML**：高级入口，把示例 `lab.yml` 解析后走同一套 API，便于迁移，不是主路径。

---

## English

<a id="english"></a>

Configuration happens on **Settings / Pipelines / Knowledge base** pages, not via a boot YAML.

- **Credentials:** one row per vector or LLM endpoint (**no separate rerank kind**); secret stored at rest (no Fernet); UI shows `key_hint` only. Plugins take `binding_id`. Runtime calls go through **LiteLLM**; a custom `base_url` maps the model to `openai/<model>`. Advanced overrides live in credential `extra`: `litellm_model`, `provider`. Real Cross-Encoders (`BAAI/bge-reranker-v2-m3`, …) need a [custom reranker plugin](custom-plugins.md).
- **Upload:** KB page → `stored_files` → `documents` → ingest. Default loader `auto` routes by strategy (text / markup / layout / table / ocr); pipelines may pin `text`, `table`, `ocr`, etc. for A/B tests. `text_file` aliases `auto`. Changing embedder/chunker requires a new collection and reingest.
- **YAML import:** advanced; parses example `lab.yml` through the same APIs. Not the primary path.
