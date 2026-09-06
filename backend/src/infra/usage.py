"""Accumulated model token / cost usage for a single RAG run."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelUsage:
    """Usage from one chat or embedding call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    # USD estimate from LiteLLM model price map (not provider invoice).
    cost_usd: float | None = None


@dataclass
class UsageAccumulator:
    """Sums ModelUsage across all model calls in a pipeline run."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float | None = None
    calls: int = 0

    def add(self, usage: ModelUsage) -> None:
        self.calls += 1
        self.prompt_tokens += max(0, int(usage.prompt_tokens or 0))
        self.completion_tokens += max(0, int(usage.completion_tokens or 0))
        self.cached_tokens += max(0, int(usage.cached_tokens or 0))
        if usage.cost_usd is not None:
            self.cost_usd = (self.cost_usd or 0.0) + float(usage.cost_usd)

    def persist_fields(self) -> dict[str, int | None]:
        """Fields for ``rag_runs`` token / cost columns.

        Returns all-null when no model calls ran. Cost stays null when LiteLLM
        has no price entry for the model (common for custom / local ids).
        """
        if self.calls == 0:
            return {
                "token_in": None,
                "token_out": None,
                "token_cached": None,
                "cost_micros": None,
            }
        cost_micros: int | None = None
        if self.cost_usd is not None:
            cost_micros = int(round(self.cost_usd * 1_000_000))
        return {
            "token_in": self.prompt_tokens,
            "token_out": self.completion_tokens,
            "token_cached": self.cached_tokens,
            "cost_micros": cost_micros,
        }
