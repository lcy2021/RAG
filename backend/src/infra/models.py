"""Unified LLM / embedding client via LiteLLM.

Credentials stay OpenAI-compatible in the UI (model + base_url + key). This
module maps them onto LiteLLM so Azure, Ollama, vLLM, and other providers share
one call path. Unsupported params are dropped by LiteLLM (`drop_params=True`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

import litellm

from infra.usage import ModelUsage

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


@dataclass
class ChatResult:
    content: str
    usage: ModelUsage = field(default_factory=ModelUsage)


@dataclass
class EmbedResult:
    vectors: list[list[float]]
    usage: ModelUsage = field(default_factory=ModelUsage)


class ChatStream:
    """Async token stream that exposes aggregated ``usage`` after exhaustion."""

    def __init__(
        self,
        chunks: AsyncIterator[Any],
        *,
        model: str,
        messages: list[dict[str, str]] | None = None,
    ) -> None:
        self.usage = ModelUsage()
        self._chunks = chunks
        self._model = model
        self._messages = messages or []
        self._parts: list[str] = []
        self._saw_provider_usage = False

    def __aiter__(self) -> ChatStream:
        return self

    async def __anext__(self) -> str:
        while True:
            try:
                chunk = await self._chunks.__anext__()
            except StopAsyncIteration:
                self.finalize()
                raise
            usage_chunk = _chunk_with_usage(chunk)
            if usage_chunk is not None:
                self._saw_provider_usage = True
                self.usage = _usage_from_response(
                    usage_chunk, model=self._model, call_type="acompletion"
                )
            text = _chunk_delta_text(chunk)
            if text:
                self._parts.append(text)
                return text

    def finalize(self) -> ModelUsage:
        """Fill usage from estimates when the provider omitted stream usage."""
        self._finalize_usage()
        return self.usage

    def _finalize_usage(self) -> None:
        if self._saw_provider_usage:
            return
        completion = "".join(self._parts)
        prompt_tokens = _estimate_tokens(model=self._model, messages=self._messages)
        completion_tokens = _estimate_tokens(model=self._model, text=completion)
        cost_usd = _cost_from_tokens(
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        self.usage = ModelUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_tokens=0,
            cost_usd=cost_usd,
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
    ) -> EmbedResult: ...

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
    ) -> ChatResult: ...

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
    ) -> ChatStream: ...


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
    ) -> EmbedResult:
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
        usage = _usage_from_response(response, model=litellm_model, call_type="aembedding")
        return EmbedResult(vectors=vectors, usage=usage)

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
    ) -> ChatResult:
        kwargs = self._chat_kwargs(
            messages=messages,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=extra,
        )
        litellm_model = str(kwargs["model"])
        try:
            response = await litellm.acompletion(**kwargs)
        except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
            raise RuntimeError(_format_litellm_error(exc)) from exc
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("chat response missing content") from exc
        usage = _usage_from_response(response, model=litellm_model, call_type="acompletion")
        return ChatResult(content=content or "", usage=usage)

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
    ) -> ChatStream:
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
        # OpenAI-compatible providers return usage on the final chunk when set.
        kwargs["stream_options"] = {"include_usage": True}
        litellm_model = str(kwargs["model"])

        async def _run() -> AsyncIterator[Any]:
            try:
                response = await litellm.acompletion(**kwargs)
            except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
                raise RuntimeError(_format_litellm_error(exc)) from exc
            try:
                async for chunk in response:
                    yield chunk
            except Exception as exc:  # noqa: BLE001 — normalize provider errors for plugins
                raise RuntimeError(_format_litellm_error(exc)) from exc

        return ChatStream(_run(), model=litellm_model, messages=messages)

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


def _usage_from_response(response: Any, *, model: str, call_type: str) -> ModelUsage:
    prompt_tokens, completion_tokens, cached_tokens = _tokens_from_usage(
        getattr(response, "usage", None)
    )
    cost_usd = _cost_usd(response, model=model, call_type=call_type)
    return ModelUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cost_usd=cost_usd,
    )


def _tokens_from_usage(usage: Any) -> tuple[int, int, int]:
    if usage is None:
        return 0, 0, 0
    if isinstance(usage, dict):
        prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
        completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
        cached = _cached_tokens_from_payload(usage)
        return prompt, completion, cached
    prompt = int(getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", None) or 0)
    completion = int(
        getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", None) or 0
    )
    cached = _cached_tokens_from_payload(usage)
    return prompt, completion, cached


def _cached_tokens_from_payload(usage: Any) -> int:
    """Prompt-cache hit tokens (OpenAI cached_tokens / Anthropic cache_read)."""
    candidates: list[Any] = []
    if isinstance(usage, dict):
        details = usage.get("prompt_tokens_details") or {}
        if isinstance(details, dict):
            candidates.append(details.get("cached_tokens"))
        candidates.extend(
            [
                usage.get("cache_read_input_tokens"),
                usage.get("_cache_read_input_tokens"),
                usage.get("cached_tokens"),
            ]
        )
    else:
        details = getattr(usage, "prompt_tokens_details", None)
        if details is not None:
            if isinstance(details, dict):
                candidates.append(details.get("cached_tokens"))
            else:
                candidates.append(getattr(details, "cached_tokens", None))
        candidates.extend(
            [
                getattr(usage, "cache_read_input_tokens", None),
                getattr(usage, "_cache_read_input_tokens", None),
                getattr(usage, "cached_tokens", None),
            ]
        )
    for value in candidates:
        if value is None:
            continue
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            continue
    return 0


def _cost_usd(response: Any, *, model: str, call_type: str) -> float | None:
    hidden = getattr(response, "_hidden_params", None)
    if isinstance(hidden, dict) and hidden.get("response_cost") is not None:
        try:
            return float(hidden["response_cost"])
        except (TypeError, ValueError):
            pass
    try:
        return float(
            litellm.completion_cost(
                completion_response=response,
                model=model,
                call_type=call_type,  # type: ignore[arg-type]
            )
        )
    except Exception:  # noqa: BLE001 — unknown custom models have no price map
        return None


def _estimate_tokens(
    *,
    model: str,
    messages: list[dict[str, str]] | None = None,
    text: str | None = None,
) -> int:
    try:
        if messages is not None:
            return int(litellm.token_counter(model=model, messages=messages) or 0)
        return int(litellm.token_counter(model=model, text=text or "") or 0)
    except Exception:  # noqa: BLE001 — tokenizer missing for some custom ids
        raw = text if text is not None else " ".join(
            str(item.get("content") or "") for item in (messages or [])
        )
        return max(0, len(raw) // 4)


def _cost_from_tokens(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float | None:
    try:
        prompt_cost, completion_cost = litellm.cost_per_token(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return float(prompt_cost) + float(completion_cost)
    except Exception:  # noqa: BLE001 — unknown custom models have no price map
        return None


def _chunk_with_usage(chunk: Any) -> Any | None:
    usage = getattr(chunk, "usage", None)
    if usage is None and isinstance(chunk, dict):
        usage = chunk.get("usage")
    return chunk if usage is not None else None


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
