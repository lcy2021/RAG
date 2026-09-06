# Custom plugins / 自定义插件

> **中文** ↓ · **[English](#english)** · [架构](../design.md) · [界面](ui.md)  
> 参考：[DeepSeek Harness 插件](https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/)（`apply` + 注册表 + schema；不引入 Cordis）

---

## 中文

自定义插件在 **插件中心上传一个 `.py` 文件**，服务端 `apply(registry)` 后出现在流水线/对比下拉框。`lab.yml` 的 `extra_plugins` 仅用于批量导入示例。

```python
from plugins import define_stage

plugin = define_stage(
    stage="query_transformer",
    name="my_hyde",
    version="1.0.0",
    description="用假设答案向量检索，缩小问句与文档文体差距。",
    config_schema={...},
    default_params={"n_hypothetical": 1},
)

@plugin.run
async def run(data, params, ctx):
    ...
    return data

def apply(registry):
    registry.register(plugin)
```

规则：`stage` 必须是现有环节；必须写 `description`（插件中心展示用途）；params 禁止 API key；改 embedding 维度要新 collection；一个 `define_stage` 只对应一个环节。

**真 rerank（如 BAAI/bge-reranker-v2-m3）：** 内置 `bge-reranker` 只是用 LLM chat 打分的占位。专用 Cross-Encoder 请写 `stage="reranker"` 的自定义插件，在 `run` 里调用 Xinference/TEI 的 `/rerank`（或 FlagEmbedding）。Settings 不提供 `rerank` 凭证类型；密钥可放环境变量，或在插件内通过你自己约定的 `binding_id`/配置解析（不要把 api_key 写进 params）。

```python
from plugins import define_stage

plugin = define_stage(
    stage="reranker",
    name="tei_bge_m3",
    version="1.0.0",
    description="调用 TEI/Xinference /rerank（BAAI/bge-reranker-v2-m3）。",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "top_n": {"type": "integer"},
            "base_url": {"type": "string"},
            "model": {"type": "string"},
        },
    },
    default_params={"top_n": 5, "model": "bge-reranker-v2-m3"},
)

@plugin.run
async def run(data, params, ctx):
    # POST {base_url}/rerank with query + documents; rewrite data["retrieved"]
    ...
    return data

def apply(registry):
    registry.register(plugin)
```

---

## English

<a id="english"></a>

Upload **one `.py` file** on the Plugin hub. The server calls `apply(registry)`; the plugin appears in pipeline/compare dropdowns. `lab.yml` `extra_plugins` is only for bulk import examples.

Harness analog: `defineTool` + `ctx.tools.register`. Injected services: `ctx.llm`, `ctx.embeddings`, `ctx.trace` — never raw keys.

Rules: stage must already exist; set `description` (purpose shown in the plugin hub); no API keys in params; new embedding dim ⇒ new collection; one `define_stage` per stage.

**Real rerank models (e.g. BAAI/bge-reranker-v2-m3):** Builtin `bge-reranker` is an LLM-chat stand-in. Ship a custom `stage="reranker"` plugin that calls Xinference/TEI `/rerank` (or FlagEmbedding). There is no `rerank` credential kind; keep secrets in env or resolve via your own `binding_id`/config — never put `api_key` in params. See the Chinese section for a sketch.
