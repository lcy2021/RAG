"""Retrieval helpers: BM25, RRF, tokenization, JSON parsing. No secrets."""

from __future__ import annotations

import json
import math
import re
from typing import Any

_LATIN = re.compile(r"[a-z0-9]+", re.I)
_CJK = re.compile(r"[\u4e00-\u9fff]+")
_SENTENCE = re.compile(r"(?<=[。！？.!?\n])")


def tokenize(text: str) -> list[str]:
    """Latin words plus CJK unigrams and bigrams (jieba-free Chinese BM25)."""
    lowered = text.lower()
    tokens = _LATIN.findall(lowered)
    for block in _CJK.findall(text):
        tokens.extend(list(block))
        tokens.extend(block[i : i + 2] for i in range(len(block) - 1))
    return tokens


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_l = math.sqrt(sum(a * a for a in left))
    norm_r = math.sqrt(sum(b * b for b in right))
    if norm_l == 0 or norm_r == 0:
        return 0.0
    return dot / (norm_l * norm_r)


def bm25_scores(
    query_tokens: list[str],
    documents: list[list[str]],
    *,
    k1: float = 1.2,
    b: float = 0.75,
) -> list[float]:
    if not documents:
        return []
    n_docs = len(documents)
    avg_len = sum(len(doc) for doc in documents) / n_docs
    df: dict[str, int] = {}
    for doc in documents:
        for term in set(doc):
            df[term] = df.get(term, 0) + 1
    scores: list[float] = []
    query_set = query_tokens
    for doc in documents:
        length = len(doc) or 1
        tf: dict[str, int] = {}
        for term in doc:
            tf[term] = tf.get(term, 0) + 1
        score = 0.0
        for term in query_set:
            freq = tf.get(term, 0)
            if freq == 0:
                continue
            n_q = df.get(term, 0)
            idf = math.log(1 + (n_docs - n_q + 0.5) / (n_q + 0.5))
            denom = freq + k1 * (1 - b + b * length / avg_len)
            score += idf * (freq * (k1 + 1) / denom)
        scores.append(score)
    return scores


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict[str, Any]]],
    *,
    k: int = 60,
    id_key: str = "chunk_id",
) -> list[dict[str, Any]]:
    """Merge ranked lists with RRF. Higher fused score is better."""
    fused: dict[Any, dict[str, Any]] = {}
    scores: dict[Any, float] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            item_id = item.get(id_key) or item.get("content")
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            if item_id not in fused:
                fused[item_id] = dict(item)
    ordered = sorted(
        fused.values(),
        key=lambda row: scores[row.get(id_key) or row.get("content")],
        reverse=True,
    )
    result = []
    for index, item in enumerate(ordered, start=1):
        cloned = dict(item)
        cloned["fused_rank"] = index
        cloned["rank"] = index
        cloned["score"] = scores[cloned.get(id_key) or cloned.get("content")]
        cloned["retriever"] = "rrf"
        result.append(cloned)
    return result


def split_sentences(text: str) -> list[str]:
    parts = [part.strip() for part in _SENTENCE.split(text) if part.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    try:
        value = json.loads(stripped)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        value = json.loads(stripped[start : end + 1])
        if isinstance(value, dict):
            return value
    raise ValueError("model did not return a JSON object")


def parse_lines(text: str, limit: int) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("0123456789.-) ").strip()
        if line:
            lines.append(line)
        if len(lines) >= limit:
            break
    return lines
