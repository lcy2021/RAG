"""Scenario and gold-span management."""

from __future__ import annotations

import csv
import io
import json
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.enums import PipelineStage
from models.schemas import (
    EvalItemCreate,
    EvalItemImportRow,
    EvalItemImportSpan,
    EvalItemOut,
    EvalItemSpanCreate,
    EvalItemSpanOut,
    EvalItemUpdate,
    ScenarioCreate,
    ScenarioDetailOut,
    ScenarioItemsImport,
    ScenarioItemsImportResult,
    ScenarioOut,
    ScenarioUpdate,
)
from plugins.registry import PluginRegistry, get_registry
from repositories.knowledge_bases import KnowledgeBaseRepository
from repositories.scenarios import ScenarioRepository


class ScenarioService:
    def __init__(self, session: AsyncSession, registry: PluginRegistry | None = None) -> None:
        self._repo = ScenarioRepository(session)
        self._kb = KnowledgeBaseRepository(session)
        self._registry = registry or get_registry()

    async def list_scenarios(self) -> list[ScenarioOut]:
        return [ScenarioOut.model_validate(row) for row in await self._repo.list_all()]

    async def get_scenario(self, scenario_id: UUID) -> ScenarioDetailOut:
        row = await self._repo.get_detail(scenario_id)
        if not row:
            raise HTTPException(status_code=404, detail="scenario not found")
        return ScenarioDetailOut.model_validate(row)

    async def create_scenario(self, payload: ScenarioCreate) -> ScenarioOut:
        if not await self._repo.kb_exists(payload.knowledge_base_id):
            raise HTTPException(status_code=400, detail="knowledge base not found")
        self._validate_metrics(payload.metric_plugins, payload.metric_weights)
        dataset_name = f"{payload.name} · gold · {uuid4().hex[:8]}"
        try:
            row = await self._repo.insert(
                name=payload.name,
                knowledge_base_id=payload.knowledge_base_id,
                dataset_name=dataset_name,
                metric_plugins=payload.metric_plugins,
                metric_weights=payload.metric_weights,
                latency_p95_ms_max=payload.latency_p95_ms_max,
                cost_micros_max=payload.cost_micros_max,
                notes=payload.notes,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="scenario name already exists") from exc
        return ScenarioOut.model_validate(row)

    async def update_scenario(self, scenario_id: UUID, payload: ScenarioUpdate) -> ScenarioOut:
        existing = await self._repo.get(scenario_id)
        if not existing:
            raise HTTPException(status_code=404, detail="scenario not found")
        self._validate_metrics(payload.metric_plugins, payload.metric_weights)
        try:
            row = await self._repo.update(
                scenario_id,
                name=payload.name,
                metric_plugins=payload.metric_plugins,
                metric_weights=payload.metric_weights,
                latency_p95_ms_max=payload.latency_p95_ms_max,
                cost_micros_max=payload.cost_micros_max,
                notes=payload.notes,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="scenario name already exists") from exc
        assert row is not None
        return ScenarioOut.model_validate(row)

    async def delete_scenario(self, scenario_id: UUID) -> None:
        if await self._repo.experiment_count(scenario_id) > 0:
            raise HTTPException(
                status_code=409,
                detail="scenario is still referenced by experiments",
            )
        try:
            deleted = await self._repo.delete(scenario_id)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="scenario is still referenced") from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="scenario not found")

    async def list_items(self, scenario_id: UUID) -> list[EvalItemOut]:
        scenario = await self._require_scenario(scenario_id)
        rows = await self._repo.list_items(scenario["dataset_id"])
        return [EvalItemOut.model_validate(row) for row in rows]

    async def create_item(self, scenario_id: UUID, payload: EvalItemCreate) -> EvalItemOut:
        scenario = await self._require_scenario(scenario_id)
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="question is required")
        row = await self._repo.insert_item(
            dataset_id=scenario["dataset_id"],
            question=question,
            expected=(payload.expected or "").strip() or None,
            metadata=payload.metadata,
        )
        return EvalItemOut.model_validate(row)

    async def update_item(
        self, scenario_id: UUID, item_id: UUID, payload: EvalItemUpdate
    ) -> EvalItemOut:
        await self._require_item(scenario_id, item_id)
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="question is required")
        row = await self._repo.update_item(
            item_id,
            question=question,
            expected=(payload.expected or "").strip() or None,
            metadata=payload.metadata,
        )
        assert row is not None
        return EvalItemOut.model_validate(row)

    async def delete_item(self, scenario_id: UUID, item_id: UUID) -> None:
        await self._require_item(scenario_id, item_id)
        deleted = await self._repo.delete_item(item_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="eval item not found")

    async def create_span(
        self, scenario_id: UUID, item_id: UUID, payload: EvalItemSpanCreate
    ) -> EvalItemSpanOut:
        scenario = await self._require_item(scenario_id, item_id)
        quote = payload.quote.strip()
        if not quote:
            raise HTTPException(status_code=400, detail="quote is required")
        if not await self._repo.document_in_kb(payload.document_id, scenario["knowledge_base_id"]):
            raise HTTPException(
                status_code=400,
                detail="document does not belong to the scenario knowledge base",
            )
        if payload.char_start is not None and payload.char_end is not None:
            if payload.char_start < 0 or payload.char_end < payload.char_start:
                raise HTTPException(status_code=400, detail="invalid char span offsets")
        row = await self._repo.insert_span(
            eval_item_id=item_id,
            document_id=payload.document_id,
            quote=quote,
            char_start=payload.char_start,
            char_end=payload.char_end,
        )
        return EvalItemSpanOut.model_validate(row)

    async def delete_span(self, scenario_id: UUID, item_id: UUID, span_id: UUID) -> None:
        await self._require_item(scenario_id, item_id)
        span = await self._repo.get_span(span_id)
        if not span or span["eval_item_id"] != item_id:
            raise HTTPException(status_code=404, detail="span not found")
        deleted = await self._repo.delete_span(span_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="span not found")

    async def import_items(
        self, scenario_id: UUID, payload: ScenarioItemsImport
    ) -> ScenarioItemsImportResult:
        scenario = await self._require_scenario(scenario_id)
        docs = await self._kb.list_documents(scenario["knowledge_base_id"])
        doc_index = self._build_document_index(docs)
        warnings: list[str] = []
        replaced = False
        if payload.replace:
            await self._repo.delete_items_for_dataset(scenario["dataset_id"])
            replaced = True

        created_items = 0
        created_spans = 0
        for index, row in enumerate(payload.items, start=1):
            question = row.question.strip()
            if not question:
                warnings.append(f"item {index}: skipped empty question")
                continue
            item = await self._repo.insert_item(
                dataset_id=scenario["dataset_id"],
                question=question,
                expected=(row.expected or "").strip() or None,
                metadata=row.metadata or {},
            )
            created_items += 1
            for span_index, span in enumerate(row.spans, start=1):
                quote = (span.quote or "").strip()
                if not quote:
                    warnings.append(f"item {index} span {span_index}: skipped empty quote")
                    continue
                document_id = self._resolve_document_id(span, doc_index)
                if document_id is None:
                    warnings.append(
                        f"item {index} span {span_index}: document not found "
                        f"({span.document_id or span.document!r})"
                    )
                    continue
                if not await self._repo.document_in_kb(
                    document_id, scenario["knowledge_base_id"]
                ):
                    warnings.append(
                        f"item {index} span {span_index}: document not in scenario KB"
                    )
                    continue
                await self._repo.insert_span(
                    eval_item_id=item["id"],
                    document_id=document_id,
                    quote=quote,
                    char_start=span.char_start,
                    char_end=span.char_end,
                )
                created_spans += 1

        if created_items == 0:
            raise HTTPException(status_code=400, detail="no valid items to import")
        return ScenarioItemsImportResult(
            created_items=created_items,
            created_spans=created_spans,
            replaced=replaced,
            warnings=warnings,
        )

    async def import_items_file(
        self,
        scenario_id: UUID,
        upload: UploadFile,
        *,
        replace: bool = False,
    ) -> ScenarioItemsImportResult:
        raw = await upload.read()
        if not raw:
            raise HTTPException(status_code=400, detail="empty upload")
        filename = (upload.filename or "").lower()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="file must be UTF-8") from exc

        if filename.endswith(".json") or text.lstrip().startswith(("{", "[")):
            items = self._parse_json_items(text)
        elif filename.endswith(".csv") or "," in text.splitlines()[0]:
            items = self._parse_csv_items(text)
        else:
            raise HTTPException(
                status_code=400,
                detail="unsupported file type; use .json or .csv",
            )
        return await self.import_items(
            scenario_id,
            ScenarioItemsImport(items=items, replace=replace),
        )

    @staticmethod
    def _build_document_index(docs: list[dict[str, Any]]) -> dict[str, UUID]:
        index: dict[str, UUID] = {}
        for doc in docs:
            doc_id = doc["id"]
            index[str(doc_id).lower()] = doc_id
            title = (doc.get("title") or "").strip()
            source = (doc.get("source_uri") or "").strip()
            if title:
                index.setdefault(title.lower(), doc_id)
            if source:
                index.setdefault(source.lower(), doc_id)
                # basename match for paths like /uploads/foo.md
                base = source.replace("\\", "/").rsplit("/", 1)[-1]
                if base:
                    index.setdefault(base.lower(), doc_id)
        return index

    @staticmethod
    def _resolve_document_id(
        span: EvalItemImportSpan, doc_index: dict[str, UUID]
    ) -> UUID | None:
        if span.document_id is not None:
            key = str(span.document_id).lower()
            if key in doc_index:
                return doc_index[key]
            # Allow raw UUID even if not in index (validated later via document_in_kb)
            return span.document_id
        ref = (span.document or "").strip()
        if not ref:
            return None
        return doc_index.get(ref.lower())

    def _parse_json_items(self, text: str) -> list[EvalItemImportRow]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc
        if isinstance(data, dict) and "items" in data:
            rows = data["items"]
        elif isinstance(data, list):
            rows = data
        else:
            raise HTTPException(
                status_code=400,
                detail='JSON must be a list or {"items": [...]}',
            )
        try:
            return [EvalItemImportRow.model_validate(row) for row in rows]
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"invalid item payload: {exc}") from exc

    def _parse_csv_items(self, text: str) -> list[EvalItemImportRow]:
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames:
            raise HTTPException(status_code=400, detail="CSV header is required")
        fields = {name.strip().lower(): name for name in reader.fieldnames if name}
        required = {"question"}
        if not required.issubset(fields):
            raise HTTPException(
                status_code=400,
                detail="CSV must include a question column (optional: expected, document, quote)",
            )
        grouped: dict[str, EvalItemImportRow] = {}
        order: list[str] = []
        last_key: str | None = None
        for line_no, raw in enumerate(reader, start=2):
            question = (raw.get(fields["question"]) or "").strip()
            expected_key = fields.get("expected")
            document_key = fields.get("document") or fields.get("document_id")
            quote_key = fields.get("quote")
            expected = (raw.get(expected_key) or "").strip() if expected_key else ""
            document = (raw.get(document_key) or "").strip() if document_key else ""
            quote = (raw.get(quote_key) or "").strip() if quote_key else ""

            if not question:
                if last_key is None:
                    continue
                key = last_key
            else:
                key = question
                if key not in grouped:
                    grouped[key] = EvalItemImportRow(
                        question=question,
                        expected=expected or None,
                        spans=[],
                    )
                    order.append(key)
                elif expected and not grouped[key].expected:
                    grouped[key].expected = expected
                last_key = key

            if quote:
                span = EvalItemImportSpan(quote=quote)
                if document:
                    try:
                        span.document_id = UUID(document)
                    except ValueError:
                        span.document = document
                grouped[key].spans.append(span)

        items = [grouped[key] for key in order]
        if not items:
            raise HTTPException(status_code=400, detail="CSV contains no questions")
        return items

    async def _require_scenario(self, scenario_id: UUID) -> dict:
        row = await self._repo.get(scenario_id)
        if not row:
            raise HTTPException(status_code=404, detail="scenario not found")
        return row

    async def _require_item(self, scenario_id: UUID, item_id: UUID) -> dict:
        scenario = await self._require_scenario(scenario_id)
        item = await self._repo.get_item(item_id)
        if not item or item["dataset_id"] != scenario["dataset_id"]:
            raise HTTPException(status_code=404, detail="eval item not found")
        return scenario

    def _validate_metrics(
        self, metric_plugins: list[str], metric_weights: dict[str, float]
    ) -> None:
        if not metric_plugins:
            raise HTTPException(status_code=400, detail="at least one metric plugin is required")
        known = {plugin.name for plugin in self._registry.list_stage(PipelineStage.EVALUATOR)}
        for name in metric_plugins:
            if name not in known:
                raise HTTPException(
                    status_code=400,
                    detail=f"unknown evaluator plugin: {name}",
                )
        for key in metric_weights:
            if key not in metric_plugins:
                raise HTTPException(
                    status_code=400,
                    detail=f"metric weight key {key} is not in metric_plugins",
                )
