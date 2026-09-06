"""Parse answer citation markers and map them to retrieved passages."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

_CITATION_RE = re.compile(r"\[(\d+)\]")


def citation_ranks(answer: str) -> list[int]:
    """Return unique citation ranks in order of first appearance."""
    seen: set[int] = set()
    ordered: list[int] = []
    for match in _CITATION_RE.finditer(answer or ""):
        rank = int(match.group(1))
        if rank not in seen:
            seen.add(rank)
            ordered.append(rank)
    return ordered


def citation_spans(answer: str) -> list[dict[str, Any]]:
    """Return every ``[n]`` span with character offsets."""
    spans: list[dict[str, Any]] = []
    for match in _CITATION_RE.finditer(answer or ""):
        spans.append(
            {
                "rank": int(match.group(1)),
                "char_start": match.start(),
                "char_end": match.end(),
                "quote": match.group(0),
            }
        )
    return spans


def normalize_sources(
    retrieved: list[dict[str, Any]], *, answer: str = ""
) -> list[dict[str, Any]]:
    """Flatten retrieved hits into API-facing source rows; mark ranks cited in answer."""
    ranks = set(citation_ranks(answer))
    sources: list[dict[str, Any]] = []
    for item in retrieved:
        rank = int(item.get("rank") or 0)
        chunk_id = item.get("chunk_id")
        sources.append(
            {
                "rank": rank,
                "chunk_id": UUID(str(chunk_id)) if chunk_id else None,
                "content": str(item.get("content") or ""),
                "score": float(item["score"]) if item.get("score") is not None else None,
                "retriever": str(item.get("retriever") or "dense"),
                "cited": rank in ranks,
            }
        )
    return sources
