"""Stage plugin definition. One define_stage call maps to one pipeline stage."""

from collections.abc import Awaitable, Callable
from typing import Any

from models.enums import PipelineStage

RunFn = Callable[[Any, dict[str, Any], Any], Awaitable[Any]]

FORBIDDEN_PARAM_KEYS = frozenset({"api_key", "api-key", "secret", "password", "token"})


class StagePlugin:
    """A single-stage plugin with JSON Schema params and an async run hook."""

    def __init__(
        self,
        *,
        stage: PipelineStage | str,
        name: str,
        version: str = "1.0.0",
        config_schema: dict[str, Any] | None = None,
        default_params: dict[str, Any] | None = None,
        description: str = "",
        source: str = "builtin",
        origin_path: str | None = None,
    ) -> None:
        self.stage = PipelineStage(stage)
        self.name = name
        self.version = version
        self.config_schema = config_schema or {
            "type": "object",
            "additionalProperties": False,
        }
        self.default_params = default_params or {}
        self.description = description
        self.source = source
        self.origin_path = origin_path
        self._run: RunFn | None = None
        self._assert_no_secret_params(self.default_params)

    def run(self, fn: RunFn) -> RunFn:
        """Decorator that binds the plugin implementation."""
        self._run = fn
        return fn

    async def execute(self, data: Any, params: dict[str, Any], ctx: Any) -> Any:
        if self._run is None:
            raise NotImplementedError(f"plugin {self.stage}/{self.name} has no run handler")
        merged = {**self.default_params, **params}
        self._assert_no_secret_params(merged)
        return await self._run(data, merged, ctx)

    @staticmethod
    def _assert_no_secret_params(params: dict[str, Any]) -> None:
        lowered = {str(key).lower() for key in params}
        overlap = lowered & FORBIDDEN_PARAM_KEYS
        if overlap:
            raise ValueError(f"plugin params must not contain secret keys: {sorted(overlap)}")


def define_stage(
    *,
    stage: PipelineStage | str,
    name: str,
    version: str = "1.0.0",
    config_schema: dict[str, Any] | None = None,
    default_params: dict[str, Any] | None = None,
    description: str = "",
    source: str = "builtin",
    origin_path: str | None = None,
) -> StagePlugin:
    """Create a stage plugin. Register it via apply(registry) or registry.register."""
    return StagePlugin(
        stage=stage,
        name=name,
        version=version,
        config_schema=config_schema,
        default_params=default_params,
        description=description,
        source=source,
        origin_path=origin_path,
    )
