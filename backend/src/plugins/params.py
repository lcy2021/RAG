"""Read plugin params without treating 0 / 0.0 as missing."""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


def param_value(params: dict[str, Any], key: str, default: T) -> T:
    """Return ``params[key]`` when present and not ``None``; otherwise ``default``."""
    if key not in params or params[key] is None:
        return default
    return params[key]  # type: ignore[return-value]


def param_int(params: dict[str, Any], key: str, default: int) -> int:
    return int(param_value(params, key, default))


def param_float(params: dict[str, Any], key: str, default: float) -> float:
    return float(param_value(params, key, default))


def retrieval_query(data: dict[str, Any]) -> str:
    """Prefer rewritten query for post-retrieval stages (rerank / grade)."""
    return str(data.get("rewritten_query") or data.get("query") or "")


def text_unit_count(text: str) -> int:
    """Chunk size units: character length (matches recursive / heading splitters)."""
    return len(text or "")
