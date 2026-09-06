"""Merge default_params ← pipeline bindings ← variant overrides."""

from typing import Any


def merge_params(
    default_params: dict[str, Any],
    pipeline_params: dict[str, Any] | None = None,
    variant_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged = dict(default_params)
    if pipeline_params:
        merged.update(pipeline_params)
    if variant_params:
        merged.update(variant_params)
    return merged
