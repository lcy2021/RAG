"""Load a custom plugin module that exposes apply(registry)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from plugins.registry import PluginRegistry


def load_plugin_file(path: Path, registry: PluginRegistry) -> None:
    """Import one .py file and call apply(registry)."""
    spec = importlib.util.spec_from_file_location(f"raglab_custom_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import plugin file: {path}")
    module = ModuleType(spec.name)
    spec.loader.exec_module(module)
    apply = getattr(module, "apply", None)
    if not callable(apply):
        raise ValueError(f"{path} must define apply(registry)")
    apply(registry)
