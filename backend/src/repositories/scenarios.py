"""scenarios, eval_datasets, eval_items, eval_item_spans."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.entities import (
    Document,
    EvalDataset,
    EvalExperiment,
    EvalItem,
    EvalItemSpan,
    KnowledgeBase,
    Scenario,
)
from db.serialize import as_dict
from repositories.base import persist, remove_by_pk


def _span_dict(span: EvalItemSpan) -> dict[str, Any]:
    return as_dict(span)


def _item_dict(item: EvalItem, spans: list[EvalItemSpan] | None = None) -> dict[str, Any]:
    data = as_dict(item)
    data["spans"] = [_span_dict(span) for span in (spans or [])]
    return data


def _scenario_dict(scenario: Scenario, *, item_count: int = 0) -> dict[str, Any]:
    data = as_dict(scenario)
    data["item_count"] = item_count
    return data


class ScenarioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def kb_exists(self, kb_id: UUID) -> bool:
        return await self._session.get(KnowledgeBase, kb_id) is not None

    async def document_in_kb(self, document_id: UUID, kb_id: UUID) -> bool:
        document = await self._session.get(Document, document_id)
        return document is not None and document.knowledge_base_id == kb_id

    async def experiment_count(self, scenario_id: UUID) -> int:
        result = await self._session.scalar(
            select(func.count())
            .select_from(EvalExperiment)
            .where(EvalExperiment.scenario_id == scenario_id)
        )
        return int(result or 0)

    async def item_counts(self, dataset_ids: list[UUID]) -> dict[UUID, int]:
        if not dataset_ids:
            return {}
        result = await self._session.execute(
            select(EvalItem.dataset_id, func.count())
            .where(EvalItem.dataset_id.in_(dataset_ids))
            .group_by(EvalItem.dataset_id)
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def _spans_by_item(self, item_ids: list[UUID]) -> dict[UUID, list[EvalItemSpan]]:
        if not item_ids:
            return {}
        result = await self._session.scalars(
            select(EvalItemSpan).where(EvalItemSpan.eval_item_id.in_(item_ids))
        )
        grouped: dict[UUID, list[EvalItemSpan]] = {}
        for span in result:
            grouped.setdefault(span.eval_item_id, []).append(span)
        return grouped

    async def list_all(self) -> list[dict[str, Any]]:
        result = await self._session.scalars(select(Scenario).order_by(Scenario.name))
        scenarios = list(result)
        counts = await self.item_counts([row.dataset_id for row in scenarios])
        return [
            _scenario_dict(row, item_count=counts.get(row.dataset_id, 0)) for row in scenarios
        ]

    async def get(self, scenario_id: UUID) -> dict[str, Any] | None:
        scenario = await self._session.get(Scenario, scenario_id)
        if scenario is None:
            return None
        counts = await self.item_counts([scenario.dataset_id])
        return _scenario_dict(scenario, item_count=counts.get(scenario.dataset_id, 0))

    async def get_detail(self, scenario_id: UUID) -> dict[str, Any] | None:
        scenario = await self._session.get(Scenario, scenario_id)
        if scenario is None:
            return None
        items = await self.list_items(scenario.dataset_id)
        data = _scenario_dict(scenario, item_count=len(items))
        data["items"] = items
        return data

    async def insert(
        self,
        *,
        name: str,
        knowledge_base_id: UUID,
        dataset_name: str,
        metric_plugins: list[str],
        metric_weights: dict[str, Any],
        latency_p95_ms_max: int | None,
        cost_micros_max: int | None,
        notes: str | None,
    ) -> dict[str, Any]:
        dataset = EvalDataset(name=dataset_name, knowledge_base_id=knowledge_base_id)
        await persist(self._session, dataset)
        scenario = Scenario(
            name=name,
            knowledge_base_id=knowledge_base_id,
            dataset_id=dataset.id,
            metric_plugins=metric_plugins,
            metric_weights=metric_weights,
            latency_p95_ms_max=latency_p95_ms_max,
            cost_micros_max=cost_micros_max,
            notes=notes,
        )
        await persist(self._session, scenario)
        return _scenario_dict(scenario, item_count=0)

    async def update(
        self,
        scenario_id: UUID,
        *,
        name: str,
        metric_plugins: list[str],
        metric_weights: dict[str, Any],
        latency_p95_ms_max: int | None,
        cost_micros_max: int | None,
        notes: str | None,
    ) -> dict[str, Any] | None:
        scenario = await self._session.get(Scenario, scenario_id)
        if scenario is None:
            return None
        scenario.name = name
        scenario.metric_plugins = metric_plugins
        scenario.metric_weights = metric_weights
        scenario.latency_p95_ms_max = latency_p95_ms_max
        scenario.cost_micros_max = cost_micros_max
        scenario.notes = notes
        await self._session.flush()
        await self._session.refresh(scenario)
        counts = await self.item_counts([scenario.dataset_id])
        return _scenario_dict(scenario, item_count=counts.get(scenario.dataset_id, 0))

    async def delete(self, scenario_id: UUID) -> bool:
        scenario = await self._session.get(Scenario, scenario_id)
        if scenario is None:
            return False
        dataset_id = scenario.dataset_id
        await self._session.delete(scenario)
        await self._session.flush()
        dataset = await self._session.get(EvalDataset, dataset_id)
        if dataset is not None:
            await self._session.delete(dataset)
            await self._session.flush()
        return True

    async def list_items(self, dataset_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(EvalItem).where(EvalItem.dataset_id == dataset_id).order_by(EvalItem.question)
        )
        items = list(result)
        spans_by_item = await self._spans_by_item([item.id for item in items])
        return [_item_dict(item, spans_by_item.get(item.id, [])) for item in items]

    async def get_item(self, item_id: UUID) -> dict[str, Any] | None:
        item = await self._session.get(EvalItem, item_id)
        if item is None:
            return None
        spans = await self._spans_by_item([item.id])
        return _item_dict(item, spans.get(item.id, []))

    async def insert_item(
        self,
        *,
        dataset_id: UUID,
        question: str,
        expected: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        item = EvalItem(
            dataset_id=dataset_id,
            question=question,
            expected=expected,
            extra_metadata=metadata,
        )
        await persist(self._session, item)
        return _item_dict(item, [])

    async def update_item(
        self,
        item_id: UUID,
        *,
        question: str,
        expected: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any] | None:
        item = await self._session.get(EvalItem, item_id)
        if item is None:
            return None
        item.question = question
        item.expected = expected
        item.extra_metadata = metadata
        await self._session.flush()
        await self._session.refresh(item)
        spans = await self._spans_by_item([item.id])
        return _item_dict(item, spans.get(item.id, []))

    async def delete_item(self, item_id: UUID) -> bool:
        return await remove_by_pk(self._session, EvalItem, item_id)

    async def delete_items_for_dataset(self, dataset_id: UUID) -> int:
        result = await self._session.scalars(
            select(EvalItem).where(EvalItem.dataset_id == dataset_id)
        )
        items = list(result)
        for item in items:
            await self._session.delete(item)
        await self._session.flush()
        return len(items)

    async def insert_span(
        self,
        *,
        eval_item_id: UUID,
        document_id: UUID,
        quote: str,
        char_start: int | None,
        char_end: int | None,
    ) -> dict[str, Any]:
        span = EvalItemSpan(
            eval_item_id=eval_item_id,
            document_id=document_id,
            quote=quote,
            char_start=char_start,
            char_end=char_end,
        )
        return await persist(self._session, span)

    async def delete_span(self, span_id: UUID) -> bool:
        return await remove_by_pk(self._session, EvalItemSpan, span_id)

    async def get_span(self, span_id: UUID) -> dict[str, Any] | None:
        span = await self._session.get(EvalItemSpan, span_id)
        return as_dict(span) if span else None
