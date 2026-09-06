# Configuration / 配置

> **中文** ↓ · **[English](#english)** · [架构](../design.md) · [界面](ui.md)

---

## 中文

配置在 **凭证 / 流水线 / 知识库** 页面完成。

- **密钥**：向量或 LLM 凭证；粘贴后以 **UTF-8** 写入 `credentials.encrypted_payload`（BYTEA，当前无额外 at-rest 加密），界面显示 `key_hint`。运行时经 **LiteLLM** 调用；有自定义 `base_url` 时模型会映射为 `openai/<model>`。高级覆盖可写在凭证 `extra`：`litellm_model`、`provider`。
- **上传**：知识库页选择文件 → `stored_files` → `documents` → ingest。默认 loader `auto` 按策略路由（text / markup / layout / table / ocr）；流水线也可单独挂 `text`、`table`、`ocr` 等做对比。换 embedding/切块时新建 collection 并重新入库。
- **自定义插件**：在 `backend/src/plugins/custom/` 直接改代码（见 [custom-plugins.md](custom-plugins.md)）；无上传入口。

---

## English

<a id="english"></a>

Configuration happens on **Credentials / Pipelines / Knowledge base** pages.

- **Credentials:** one row per vector or LLM endpoint; secret stored as **UTF-8** bytes in `credentials.encrypted_payload` (BYTEA; no extra at-rest encryption today); UI shows `key_hint`. Runtime calls go through **LiteLLM**; a custom `base_url` maps the model to `openai/<model>`. Advanced overrides live in credential `extra`: `litellm_model`, `provider`.
- **Upload:** KB page → `stored_files` → `documents` → ingest. Default loader `auto` routes by strategy (text / markup / layout / table / ocr); pipelines may pin `text`, `table`, `ocr`, etc. for A/B tests. Changing embedder/chunker uses a new collection and reingest.
- **Custom plugins:** edit code under `backend/src/plugins/custom/` (see [custom-plugins.md](custom-plugins.md)); no upload UI.
