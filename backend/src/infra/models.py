"""Unified LLM / embedding client via LiteLLM.

Credentials stay OpenAI-compatible in the UI (model + base_url + key). This
module maps them onto LiteLLM so Azure, Ollama, vLLM, and other providers share
one call path. Unsupported params are dropped by LiteLLM (`drop_params=True`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol

import litellm

# Drop provider-unsupported keys (e.g. temperature on some gpt-5 / o-series models).
litellm.drop_params = True

_RESERVED_EXTRA = frozenset(
    {
        "dim",
        "batch_size",
        "litellm_model",
        "provider",
        "api_version",
    }
)


class ModelClient(Protocol):
    """Async chat + embedding surface used by PluginContext."""

    async def embed(
        self,
        *,
        texts: list[str],
        model: str,
        api_key: str,
        base_url: str | None,
        extra: dict[str, Any] | None = None,
    ) -> list[list[float]]: ...

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        extra: dict[str, Any] | None = None,
    ) -> str: ...

    def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]: ...


def resolve_litellm_model(
    model: str,
    base_url: str | None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Map credential model_name (+ optional extra) to a LiteLLM model id.

    - ``extra.litellm_model`` wins (full LiteLLM id, e.g. ``azure/my-deploy``).
    - ``extra.provider`` prefixes bare names (e.g. ``ollama`` + ``llama3`` → ``ollama/llama3``).
    - Names that already contain a provider slash are left unchanged.
    - Otherwise a custom ``base_url`` uses the OpenAI-compatible route ``openai/<model>``.
    """
    meta = extra or {}
    override = meta.get("litellm_model")
    if override:
        return str(override)

    name = model.strip()
    provider = meta.get("provider")
    if provider:
        prefix = str(provider).rstrip("/")
        if "/" in name:
            return name
        return f"{prefix}/{name}"

    if "/" in name:
        return name
    if base_url:
        return f"openai/{name}"
    return name


def _passthrough_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return {}
    return {k: v for k, v in extra.items() if k not in _RESERVED_EXTRA}


class LiteLLMClient:
    """LiteLLM-backed ModelClient for chat completions and embeddings."""

    def __init__(self, timeout_s: float = 60.0) -> None:
        self._timeout_s = timeout_s

    async def embed(
        self,
        *,
        texts: list[str],
        model: str,
        api_key: str,
        base_url: str | None,
        extra: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        litellm_model = resolve_litellm_model(model, base_url, extra)
        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "input": texts,
            "api_key": api_key,
            "timeout": self._timeout_s,
            **_passthrough_extra(extra),
        }
        if base_url:
            kwargs["api_base"] = base_url.rstrip("/")
        try:
            response = await litellm.aembedding(**kwargs)
        except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
            raise RuntimeError(_format_litellm_error(exc)) from exc
        items = sorted(response.data, key=lambda row: int(getattr(row, "index", 0) or 0))
        vectors: list[list[float]] = []
        for row in items:
            embedding = getattr(row, "embedding", None)
            if embedding is None and isinstance(row, dict):
                embedding = row.get("embedding")
            if embedding is None:
                raise RuntimeError("embedding response missing vectors")
            vectors.append(list(embedding))
        return vectors

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        extra: dict[str, Any] | None = None,
    ) -> str:
        kwargs = self._chat_kwargs(
            messages=messages,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        )
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
            raise RuntimeError(_format_litellm_error(exc)) from exc
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("chat response missing content") from exc
        return content or ""

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        extra: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        kwargs = self._chat_kwargs(
            messages=messages,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        )
        kwargs["stream"] = True
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
            raise RuntimeError(_format_litellm_error(exc)) from exc
        try:
            async for chunk in response:
                text = _chunk_delta_text(chunk)
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
            raise RuntimeError(_format_litellm_error(exc)) from exc

    def _chat_kwargs(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        api_key: str,
        base_url: str | None,
        temperature: float,
        max_tokens: int,
        extra: dict[str, Any] | None,
    ) -> dict[str, Any]:
        litellm_model = resolve_litellm_model(model, base_url, extra)
        kwargs: dict[str, Any] = {
            "model": litellm_model,
            "messages": messages,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self._timeout_s,
            **_passthrough_extra(extra),
        }
        if base_url:
            kwargs["api_base"] = base_url.rstrip("/")
        return kwargs


def _chunk_delta_text(chunk: Any) -> str:
    try:
        delta = chunk.choices[0].delta
    except (AttributeError, IndexError, KeyError, TypeError):
        return ""
    content = getattr(delta, "content", None)
    if content is None and isinstance(delta, dict):
        content = delta.get("content")
    return content or ""


def _format_litellm_error(exc: BaseException) -> str:
    status = getattr(exc, "status_code", None)
    message = str(exc).strip() or exc.__class__.__name__
    if len(message) > 500:
        message = message[:500] + "…"
    if status is not None:
        return f"model HTTP {status}: {message}"
    return f"model error: {message}"
