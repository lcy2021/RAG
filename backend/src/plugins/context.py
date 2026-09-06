"""Injected plugin context. Implementations must never expose raw API keys."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from infra.models import LiteLLMClient
from infra.usage import UsageAccumulator
from repositories.knowledge_bases import KnowledgeBaseRepository
from services.bindings import BindingResolver, ResolvedBinding

TokenCallback = Callable[[str], Awaitable[None]]


class TraceSink(Protocol):
    def span(self, stage: str, plugin_name: str, payload: dict[str, Any]) -> None: ...


@dataclass
class SpanRecord:
    stage: str
    plugin_name: str
    ordinal: int
    latency_ms: int | None
    output: dict[str, Any] | None
    error_message: str | None = None


class MemoryTrace:
    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []

    def record(self, span: SpanRecord) -> None:
        self.spans.append(span)


@dataclass
class PluginContext:
    """Services passed into plugin.run. Bindings resolve credentials off-params."""

    resolver: BindingResolver
    kb_repo: KnowledgeBaseRepository
    models: LiteLLMClient
    trace: MemoryTrace
    default_embedder_binding_id: UUID | None = None
    default_generator_binding_id: UUID | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    usage: UsageAccumulator = field(default_factory=UsageAccumulator)

    async def resolve_binding(self, binding_id: UUID | str | None) -> ResolvedBinding:
        if binding_id is None:
            raise ValueError("binding_id is required")
        return await self.resolver.resolve(UUID(str(binding_id)))

    async def embed_texts(
        self, texts: list[str], binding_id: UUID | str | None
    ) -> list[list[float]]:
        target = binding_id or self.default_embedder_binding_id
        binding = await self.resolve_binding(target)
        result = await self.models.embed(
            texts=texts,
            model=binding.model_name,
            api_key=binding.api_key,
            base_url=binding.base_url,
            extra=binding.extra,
        )
        self.usage.add(result.usage)
        return result.vectors

    async def chat_complete(
        self,
        messages: list[dict[str, str]],
        binding_id: UUID | str | None,
        *,
        temperature: float,
        max_tokens: int,
    ) -> str:
        target = binding_id or self.default_generator_binding_id
        binding = await self.resolve_binding(target)
        result = await self.models.chat(
            messages=messages,
            model=binding.model_name,
            api_key=binding.api_key,
            base_url=binding.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=binding.extra,
        )
        self.usage.add(result.usage)
        return result.content

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        binding_id: UUID | str | None,
        *,
        temperature: float,
        max_tokens: int,
    ) -> AsyncIterator[str]:
        target = binding_id or self.default_generator_binding_id
        binding = await self.resolve_binding(target)
        stream = self.models.chat_stream(
            messages=messages,
            model=binding.model_name,
            api_key=binding.api_key,
            base_url=binding.base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            extra=binding.extra,
        )
        try:
            async for delta in stream:
                yield delta
        finally:
            stream.finalize()
            self.usage.add(stream.usage)

    def token_callback(self) -> TokenCallback | None:
        callback = self.extra.get("on_token")
        return callback if callable(callback) else None
