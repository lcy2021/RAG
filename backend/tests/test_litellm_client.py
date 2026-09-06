"""Unit tests for LiteLLM model id mapping and client wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from infra.models import LiteLLMClient, resolve_litellm_model
from infra.usage import UsageAccumulator


@pytest.mark.parametrize(
    ("model", "base_url", "extra", "expected"),
    [
        ("gpt-4o", None, None, "gpt-4o"),
        ("bge-m3", "http://localhost:11434/v1", None, "openai/bge-m3"),
        ("gpt-5.4", "https://example.openai.azure.com/openai/v1", None, "openai/gpt-5.4"),
        ("azure/my-deploy", "https://example.openai.azure.com", None, "azure/my-deploy"),
        ("llama3", None, {"provider": "ollama"}, "ollama/llama3"),
        ("bge-m3", "http://x/v1", {"litellm_model": "ollama/bge-m3"}, "ollama/bge-m3"),
    ],
)
def test_resolve_litellm_model(model, base_url, extra, expected):
    assert resolve_litellm_model(model, base_url, extra) == expected


def test_usage_accumulator_persist_fields():
    empty = UsageAccumulator()
    assert empty.persist_fields() == {
        "token_in": None,
        "token_out": None,
        "token_cached": None,
        "cost_micros": None,
    }

    acc = UsageAccumulator()
    from infra.usage import ModelUsage

    acc.add(ModelUsage(prompt_tokens=10, completion_tokens=5, cached_tokens=4, cost_usd=0.000012))
    acc.add(ModelUsage(prompt_tokens=2, completion_tokens=3, cached_tokens=1, cost_usd=None))
    fields = acc.persist_fields()
    assert fields["token_in"] == 12
    assert fields["token_out"] == 8
    assert fields["token_cached"] == 5
    assert fields["cost_micros"] == 12


@pytest.mark.asyncio
async def test_chat_uses_litellm_acompletion():
    client = LiteLLMClient(timeout_s=12)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
        usage=SimpleNamespace(
            prompt_tokens=3,
            completion_tokens=2,
            prompt_tokens_details=SimpleNamespace(cached_tokens=1),
        ),
        _hidden_params={"response_cost": 0.0001},
    )
    with patch("infra.models.litellm.acompletion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = response
        result = await client.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4",
            api_key="sk-test",
            base_url="https://example.openai.azure.com/openai/v1",
            temperature=0.2,
            max_tokens=256,
        )
    assert result.content == "hello"
    assert result.usage.prompt_tokens == 3
    assert result.usage.completion_tokens == 2
    assert result.usage.cached_tokens == 1
    assert result.usage.cost_usd == 0.0001
    kwargs = mock_chat.await_args.kwargs
    assert kwargs["model"] == "openai/gpt-5.4"
    assert kwargs["api_base"] == "https://example.openai.azure.com/openai/v1"
    assert kwargs["api_key"] == "sk-test"
    assert kwargs["max_tokens"] == 256
    assert kwargs["timeout"] == 12


@pytest.mark.asyncio
async def test_embed_uses_litellm_aembedding():
    client = LiteLLMClient()
    response = SimpleNamespace(
        data=[
            SimpleNamespace(index=1, embedding=[0.0, 1.0]),
            SimpleNamespace(index=0, embedding=[1.0, 0.0]),
        ],
        usage=SimpleNamespace(prompt_tokens=4, completion_tokens=0),
        _hidden_params={},
    )
    with patch("infra.models.litellm.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = response
        with patch("infra.models.litellm.completion_cost", side_effect=Exception("no price")):
            result = await client.embed(
                texts=["a", "b"],
                model="bge-m3",
                api_key="ollama",
                base_url="http://localhost:11434/v1",
                extra={"dim": 1024, "batch_size": 8},
            )
    assert result.vectors == [[1.0, 0.0], [0.0, 1.0]]
    assert result.usage.prompt_tokens == 4
    kwargs = mock_embed.await_args.kwargs
    assert kwargs["model"] == "openai/bge-m3"
    assert "dim" not in kwargs
    assert "batch_size" not in kwargs


@pytest.mark.asyncio
async def test_chat_stream_uses_litellm_acompletion():
    client = LiteLLMClient(timeout_s=12)

    async def fake_stream(**_kwargs):
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="hel"))])
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content="lo"))])
        yield SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=2),
            _hidden_params={"response_cost": 0.0002},
        )

    with patch("infra.models.litellm.acompletion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_stream()
        stream = client.chat_stream(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4",
            api_key="sk-test",
            base_url="https://example.openai.azure.com/openai/v1",
            temperature=0.2,
            max_tokens=256,
        )
        parts = [text async for text in stream]
    assert parts == ["hel", "lo"]
    assert stream.usage.prompt_tokens == 7
    assert stream.usage.completion_tokens == 2
    assert stream.usage.cost_usd == 0.0002
    kwargs = mock_chat.await_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}
    assert kwargs["model"] == "openai/gpt-5.4"
    assert kwargs["api_base"] == "https://example.openai.azure.com/openai/v1"


@pytest.mark.asyncio
async def test_chat_wraps_provider_errors():
    client = LiteLLMClient()
    with patch("infra.models.litellm.acompletion", new_callable=AsyncMock) as mock_chat:
        err = RuntimeError("bad request")
        err.status_code = 400  # type: ignore[attr-defined]
        mock_chat.side_effect = err
        with pytest.raises(RuntimeError, match="model HTTP 400"):
            await client.chat(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-4o",
                api_key="sk",
                base_url=None,
            )
