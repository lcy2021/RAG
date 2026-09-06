"""Unit tests for LiteLLM model id mapping and client wiring."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from infra.models import LiteLLMClient, resolve_litellm_model


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


@pytest.mark.asyncio
async def test_chat_uses_litellm_acompletion():
    client = LiteLLMClient(timeout_s=12)
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))]
    )
    with patch("infra.models.litellm.acompletion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = response
        text = await client.chat(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4",
            api_key="sk-test",
            base_url="https://example.openai.azure.com/openai/v1",
            temperature=0.2,
            max_tokens=256,
        )
    assert text == "hello"
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
        ]
    )
    with patch("infra.models.litellm.aembedding", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = response
        vectors = await client.embed(
            texts=["a", "b"],
            model="bge-m3",
            api_key="ollama",
            base_url="http://localhost:11434/v1",
            extra={"dim": 1024, "batch_size": 8},
        )
    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
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
        yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=None))])

    with patch("infra.models.litellm.acompletion", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = fake_stream()
        parts = [
            text
            async for text in client.chat_stream(
                messages=[{"role": "user", "content": "hi"}],
                model="gpt-5.4",
                api_key="sk-test",
                base_url="https://example.openai.azure.com/openai/v1",
                temperature=0.2,
                max_tokens=256,
            )
        ]
    assert parts == ["hel", "lo"]
    kwargs = mock_chat.await_args.kwargs
    assert kwargs["stream"] is True
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

