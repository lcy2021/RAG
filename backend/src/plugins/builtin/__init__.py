"""Builtin catalog aligned with ingest + query stages."""

from plugins.builtin.chunker import CHUNKER_PLUGINS
from plugins.builtin.compressor import COMPRESSOR_PLUGINS
from plugins.builtin.embedder import EMBEDDER_PLUGINS
from plugins.builtin.evaluator import EVALUATOR_PLUGINS
from plugins.builtin.fusion import FUSION_PLUGINS
from plugins.builtin.generator import GENERATOR_PLUGINS
from plugins.builtin.grader import GRADER_PLUGINS
from plugins.builtin.indexer import INDEXER_PLUGINS
from plugins.builtin.loader_stage import LOADER_PLUGINS
from plugins.builtin.query_transformer import QUERY_TRANSFORMER_PLUGINS
from plugins.builtin.reranker import RERANKER_PLUGINS
from plugins.builtin.retriever import RETRIEVER_PLUGINS
from plugins.define import StagePlugin
from plugins.registry import PluginRegistry

ALL_BUILTIN_PLUGINS: list[StagePlugin] = [
    *LOADER_PLUGINS,
    *CHUNKER_PLUGINS,
    *EMBEDDER_PLUGINS,
    *INDEXER_PLUGINS,
    *QUERY_TRANSFORMER_PLUGINS,
    *RETRIEVER_PLUGINS,
    *FUSION_PLUGINS,
    *RERANKER_PLUGINS,
    *GRADER_PLUGINS,
    *COMPRESSOR_PLUGINS,
    *GENERATOR_PLUGINS,
    *EVALUATOR_PLUGINS,
]


def register_builtin(registry: PluginRegistry) -> None:
    for plugin in ALL_BUILTIN_PLUGINS:
        registry.register(plugin)
