from plugins.define import define_stage

chat = define_stage(
    stage="generator",
    name="chat",
    config_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "binding_id": {"type": "string"},
            "temperature": {"type": "number"},
            "max_tokens": {"type": "integer"},
        },
    },
    default_params={"temperature": 0.2, "max_tokens": 1024},
    description="根据检索段落生成回答；引用集中在段末；资料不足时应明确说不知道。",
)


@chat.run
async def run_chat(data, params, ctx):
    retrieved = data.get("retrieved") or []
    context_blocks = []
    for item in retrieved:
        context_blocks.append(f"[{item.get('rank')}] {item.get('content')}")
    context = "\n\n".join(context_blocks) if context_blocks else "(no retrieved passages)"
    query = data.get("query") or ""
    history = data.get("history") or []
    messages = [
        {
            "role": "system",
            "content": (
                "Answer using ONLY the retrieved passages. "
                "Write in clear paragraphs. Place citation markers only at the end of "
                "each paragraph that uses retrieved evidence, e.g. ...text. [1][3] "
                "Do not cite after every sentence or mid-sentence. "
                "Use matching bracket numbers from the passages; do not invent numbers. "
                "If the passages are insufficient, say you do not know and do not cite. "
                "Do not mention API keys."
            ),
        }
    ]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": f"Question:\n{query}\n\nPassages:\n{context}",
        }
    )
    temperature = float(params.get("temperature") or 0.2)
    max_tokens = int(params.get("max_tokens") or 1024)
    binding_id = params.get("binding_id")
    on_token = ctx.token_callback()
    if on_token is None:
        answer = await ctx.chat_complete(
            messages,
            binding_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        parts: list[str] = []
        async for delta in ctx.chat_stream(
            messages,
            binding_id,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            parts.append(delta)
            await on_token(delta)
        answer = "".join(parts)
    data["answer"] = answer
    return data


GENERATOR_PLUGINS = [chat]
