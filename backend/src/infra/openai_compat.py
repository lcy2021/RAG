"""Backward-compatible alias; prefer ``infra.models.LiteLLMClient``. """

from infra.models import LiteLLMClient as OpenAICompatClient

__all__ = ["OpenAICompatClient"]
