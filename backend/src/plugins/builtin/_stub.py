"""Helpers for catalog stubs. Real run logic is added per milestone."""

from collections.abc import Mapping
from typing import Any

from plugins.define import StagePlugin, define_stage


def stub_plugin(
    stage: str,
    name: str,
    *,
    config_schema: Mapping[str, Any] | None = None,
    default_params: Mapping[str, Any] | None = None,
    description: str = "",
) -> StagePlugin:
    plugin = define_stage(
        stage=stage,
        name=name,
        config_schema=dict(config_schema or {"type": "object", "additionalProperties": False}),
        default_params=dict(default_params or {}),
        description=description,
    )

    @plugin.run
    async def run(data: Any, params: dict[str, Any], ctx: Any) -> Any:
        raise NotImplementedError(f"{stage}/{name} is not implemented yet")

    return plugin


OBJECT_SCHEMA: dict[str, Any] = {"type": "object", "additionalProperties": False}
