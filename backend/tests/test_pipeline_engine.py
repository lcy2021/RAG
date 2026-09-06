from engine.runner import ordered_calls
from engine.textsplit import split_recursive
from models.enums import PipelineKind
from plugins.define import define_stage
from plugins.registry import PluginRegistry


def test_split_recursive_respects_size_and_overlap() -> None:
    text = "alpha beta gamma delta epsilon zeta"
    chunks = split_recursive(text, chunk_size=20, overlap=4)
    assert chunks
    assert all(len(chunk) <= 24 for chunk in chunks)


def test_ordered_calls_uses_first_binding_and_overrides() -> None:
    slots = [
        {
            "stage": "query_transformer",
            "bindings": [{"name": "passthrough", "params": {}}],
        },
        {
            "stage": "retriever",
            "bindings": [{"name": "dense", "params": {"top_k": 5}}],
        },
        {
            "stage": "generator",
            "bindings": [{"name": "chat", "params": {}}],
        },
    ]
    calls = ordered_calls(slots, PipelineKind.QUERY)
    names = [(item["stage"], item["plugin"]) for item in calls]
    assert names[0] == ("query_transformer", "passthrough")
    assert names[-1] == ("generator", "chat")
    overridden = ordered_calls(
        slots,
        PipelineKind.QUERY,
        {"query_transformer": {"plugin": "hyde", "params": {"n_hypothetical": 1}}},
    )
    assert overridden[0]["plugin"] == "hyde"


async def test_passthrough_sets_rewritten_query() -> None:
    plugin = PluginRegistry()
    stage = define_stage(stage="query_transformer", name="echo")

    @stage.run
    async def run(data, params, ctx):
        data["rewritten_query"] = data["query"]
        return data

    plugin.register(stage)
    found = plugin.get("query_transformer", "echo")
    assert found is not None
    result = await found.execute({"query": "hello"}, {}, None)
    assert result["rewritten_query"] == "hello"


async def test_run_pipeline_emits_progress() -> None:
    from engine.runner import run_pipeline
    from plugins.context import MemoryTrace, PluginContext

    registry = PluginRegistry()
    stage = define_stage(stage="query_transformer", name="echo")

    @stage.run
    async def run(data, params, ctx):
        data["rewritten_query"] = data["query"]
        return data

    registry.register(stage)
    events: list[dict] = []

    async def on_progress(event: dict) -> None:
        events.append(event)

    ctx = PluginContext(
        resolver=None,  # type: ignore[arg-type]
        kb_repo=None,  # type: ignore[arg-type]
        models=None,  # type: ignore[arg-type]
        trace=MemoryTrace(),
    )
    result = await run_pipeline(
        calls=[
            {
                "stage": "query_transformer",
                "plugin": "echo",
                "params": {},
                "ordinal": 0,
            }
        ],
        data={"query": "hello"},
        ctx=ctx,
        registry=registry,
        on_progress=on_progress,
    )
    assert result["rewritten_query"] == "hello"
    assert [item["status"] for item in events] == ["running", "done"]
    assert events[0]["plugin_name"] == "echo"
    assert events[1]["output"]["rewritten_query"] == "hello"
