"""Ingest loaders: auto router plus specialized strategies for A/B tests.

Pipeline default is ``auto``. Catalog also registers ``text`` / ``markup`` /
``layout`` / ``table`` / ``ocr`` so labs can pin one strategy.
"""

from __future__ import annotations

from typing import Any

from engine.doc_extract import LoaderStrategy, load_from_ingest_data
from plugins.define import define_stage

_EMPTY_SCHEMA = {"type": "object", "additionalProperties": False}

_TABLE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "merge_tables": {
            "type": "boolean",
            "description": "Merge sheets/tables that share the same header row.",
        }
    },
}

_OCR_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ocr_lang": {
            "type": "string",
            "description": "Tesseract language pack id, e.g. chi_sim+eng.",
        }
    },
}


def _apply_result(data: dict[str, Any], result) -> dict[str, Any]:
    # Downstream chunker / KB persistence read ``raw_text``.
    data["raw_text"] = result.text
    data["loader_kind"] = result.kind.value
    data["loader_strategy"] = result.strategy.value
    if result.tables_merged:
        data["tables_merged"] = result.tables_merged
    if result.warnings:
        data["loader_warnings"] = list(result.warnings)
    return data


def _make_loader(
    *,
    name: str,
    description: str,
    force_strategy: LoaderStrategy | None,
    config_schema: dict[str, Any] | None = None,
    default_params: dict[str, Any] | None = None,
):
    plugin = define_stage(
        stage="loader",
        name=name,
        config_schema=config_schema or _EMPTY_SCHEMA,
        default_params=default_params or {},
        description=description,
    )

    @plugin.run
    async def run_loader(data, params, ctx):
        merge_tables = bool(params.get("merge_tables", True))
        ocr_lang = str(params["ocr_lang"]) if params.get("ocr_lang") is not None else "chi_sim+eng"
        result = load_from_ingest_data(
            data,
            force_strategy=force_strategy,
            merge_tables=merge_tables,
            ocr_lang=ocr_lang,
        )
        return _apply_result(data, result)

    return plugin


auto = _make_loader(
    name="auto",
    description=(
        "按扩展名/MIME 自动路由：text、markup(html)、layout(pdf/docx/pptx)、"
        "table(csv/xlsx，同表头合并)、ocr(图片/扫描 PDF)。默认入库入口。"
    ),
    force_strategy=None,
)

text = _make_loader(
    name="text",
    description="纯文本策略：txt/md/yaml/json 等；json 会格式化后入库。",
    force_strategy=LoaderStrategy.TEXT,
)

markup = _make_loader(
    name="markup",
    description="标记文档策略：抽取 HTML 可见文本，去掉 script/style。",
    force_strategy=LoaderStrategy.MARKUP,
)

layout = _make_loader(
    name="layout",
    description="版式文档策略：抽取 PDF/DOCX/PPTX 文字层（不做 OCR）。",
    force_strategy=LoaderStrategy.LAYOUT,
)

table = _make_loader(
    name="table",
    description="表格策略：CSV/XLSX（及 DOCX 表）；默认同表头多 sheet/表合并。",
    force_strategy=LoaderStrategy.TABLE,
    config_schema=_TABLE_SCHEMA,
    default_params={"merge_tables": True},
)

ocr = _make_loader(
    name="ocr",
    description=(
        "OCR 策略：图片与扫描 PDF。需 pip install 'raglab[ocr]' "
        "及本机 Tesseract（扫描 PDF 还需 poppler）。"
    ),
    force_strategy=LoaderStrategy.OCR,
    config_schema=_OCR_SCHEMA,
    default_params={"ocr_lang": "chi_sim+eng"},
)

LOADER_PLUGINS = [auto, text, markup, layout, table, ocr]
