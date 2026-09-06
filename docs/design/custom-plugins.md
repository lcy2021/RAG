# Custom plugins / 自定义插件

> **中文** ↓ · **[English](#english)** · [架构](../design.md) · [界面](ui.md)  
> 参考：[DeepSeek Harness 插件](https://deepseek-harness.github.io/deepseek-harness/en/develop/basic/)（`apply` + 注册表 + schema；不引入 Cordis）

---

## 中文

把 `.py` 写在 `backend/src/plugins/custom/`（或改 builtin），进程启动时 `apply(registry)` 并写入插件目录，出现在流水线/实验下拉框。没有上传入口，就地改代码即可。

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

约定：`stage` 为现有环节；写 `description`（插件中心展示用途）；凭证用 `binding_id`（或环境变量）；改 embedding 维度时新建 collection；一个 `define_stage` 对应一个环节。

**示例：TEI / Xinference Cross-Encoder reranker**

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

Edit `.py` under `backend/src/plugins/custom/` (or builtin). On boot the server calls `apply(registry)` and upserts the catalog; the plugin appears in pipeline/experiment dropdowns. There is no upload UI—change the code in place.

Harness analog: `defineTool` + `ctx.tools.register`. Injected services: `ctx.llm`, `ctx.embeddings`, `ctx.trace`.

Rules: stage must already exist; set `description` (shown in the plugin hub); resolve credentials with `binding_id` (or env); new embedding dim ⇒ new collection; one `define_stage` per stage.

**Example: TEI / Xinference Cross-Encoder reranker** — see the Chinese section for the sketch (`stage="reranker"`, call `/rerank`).
