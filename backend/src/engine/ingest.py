"""Ingest pipeline runner (loader → chunker → embedder → indexer)."""

from engine.runner import INGEST_ORDER, ordered_calls, run_pipeline

__all__ = ["INGEST_ORDER", "ordered_calls", "run_pipeline"]
