"""In-process plugin catalog. Persistence to the plugins table comes later."""

from models.enums import PipelineStage
from plugins.define import StagePlugin


class PluginRegistry:
    """Keyed by (stage, name). Last register for the same key wins."""

    def __init__(self) -> None:
        self._plugins: dict[tuple[PipelineStage, str], StagePlugin] = {}

    def register(self, plugin: StagePlugin) -> None:
        self._plugins[(plugin.stage, plugin.name)] = plugin

    def get(self, stage: PipelineStage | str, name: str) -> StagePlugin | None:
        return self._plugins.get((PipelineStage(stage), name))

    def list_all(self) -> list[StagePlugin]:
        return sorted(self._plugins.values(), key=lambda p: (p.stage.value, p.name))

    def list_stage(self, stage: PipelineStage | str) -> list[StagePlugin]:
        wanted = PipelineStage(stage)
        return [plugin for plugin in self.list_all() if plugin.stage == wanted]


_REGISTRY = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _REGISTRY
