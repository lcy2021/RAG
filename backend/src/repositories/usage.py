"""Aggregate token / cost usage from rag_runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.entities import Conversation, EvalExperiment, EvalRun, RagRun
from models.enums import RunStatus


def _sum_int(column: Any) -> Any:
    return func.coalesce(func.sum(column), 0)


class UsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def summary(self) -> dict[str, Any]:
        scope = case(
            (RagRun.conversation_id.is_not(None), "chat"),
            (RagRun.eval_run_id.is_not(None), "experiment"),
            else_="other",
        ).label("scope")
        stmt = (
            select(
                scope,
                func.count().label("run_count"),
                _sum_int(RagRun.token_in).label("token_in"),
                _sum_int(RagRun.token_out).label("token_out"),
                _sum_int(RagRun.token_cached).label("token_cached"),
                func.sum(RagRun.cost_micros).label("cost_micros"),
            )
            .where(RagRun.status.in_([RunStatus.SUCCEEDED, RunStatus.FAILED]))
            .group_by(scope)
        )
        rows = (await self._session.execute(stmt)).all()
        buckets = {
            "chat": _empty_bucket(),
            "experiment": _empty_bucket(),
            "total": _empty_bucket(),
        }
        for row in rows:
            key = str(row.scope)
            if key not in ("chat", "experiment"):
                continue
            bucket = {
                "run_count": int(row.run_count or 0),
                "token_in": int(row.token_in or 0),
                "token_out": int(row.token_out or 0),
                "token_cached": int(row.token_cached or 0),
                "cost_micros": int(row.cost_micros) if row.cost_micros is not None else None,
            }
            buckets[key] = bucket
            buckets["total"] = _merge_buckets(buckets["total"], bucket)
        return buckets

    async def list_conversations(self) -> list[dict[str, Any]]:
        stmt = (
            select(
                Conversation.id.label("conversation_id"),
                Conversation.title,
                Conversation.knowledge_base_id,
                Conversation.pipeline_config_id,
                Conversation.updated_at,
                func.count(RagRun.id).label("run_count"),
                _sum_int(RagRun.token_in).label("token_in"),
                _sum_int(RagRun.token_out).label("token_out"),
                _sum_int(RagRun.token_cached).label("token_cached"),
                func.sum(RagRun.cost_micros).label("cost_micros"),
                func.max(RagRun.created_at).label("last_run_at"),
            )
            .select_from(Conversation)
            .join(RagRun, RagRun.conversation_id == Conversation.id)
            .where(RagRun.status.in_([RunStatus.SUCCEEDED, RunStatus.FAILED]))
            .group_by(
                Conversation.id,
                Conversation.title,
                Conversation.knowledge_base_id,
                Conversation.pipeline_config_id,
                Conversation.updated_at,
            )
            .order_by(func.max(RagRun.created_at).desc())
        )
        result = await self._session.execute(stmt)
        return [_conversation_row(row) for row in result.all()]

    async def list_experiments(self) -> list[dict[str, Any]]:
        stmt = (
            select(
                EvalExperiment.id.label("experiment_id"),
                EvalExperiment.name.label("experiment_name"),
                func.count(func.distinct(EvalRun.id)).label("eval_run_count"),
                func.count(RagRun.id).label("run_count"),
                _sum_int(RagRun.token_in).label("token_in"),
                _sum_int(RagRun.token_out).label("token_out"),
                _sum_int(RagRun.token_cached).label("token_cached"),
                func.sum(RagRun.cost_micros).label("cost_micros"),
                func.max(RagRun.created_at).label("last_run_at"),
            )
            .select_from(RagRun)
            .join(EvalRun, EvalRun.id == RagRun.eval_run_id)
            .join(EvalExperiment, EvalExperiment.id == EvalRun.experiment_id)
            .where(RagRun.status.in_([RunStatus.SUCCEEDED, RunStatus.FAILED]))
            .group_by(EvalExperiment.id, EvalExperiment.name)
            .order_by(func.max(RagRun.created_at).desc())
        )
        result = await self._session.execute(stmt)
        return [_experiment_row(row) for row in result.all()]


def _empty_bucket() -> dict[str, Any]:
    return {
        "run_count": 0,
        "token_in": 0,
        "token_out": 0,
        "token_cached": 0,
        "cost_micros": None,
    }


def _merge_buckets(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_cost = left.get("cost_micros")
    right_cost = right.get("cost_micros")
    cost: int | None
    if left_cost is None and right_cost is None:
        cost = None
    else:
        cost = int(left_cost or 0) + int(right_cost or 0)
    return {
        "run_count": int(left.get("run_count") or 0) + int(right.get("run_count") or 0),
        "token_in": int(left.get("token_in") or 0) + int(right.get("token_in") or 0),
        "token_out": int(left.get("token_out") or 0) + int(right.get("token_out") or 0),
        "token_cached": int(left.get("token_cached") or 0) + int(right.get("token_cached") or 0),
        "cost_micros": cost,
    }


def _conversation_row(row: Any) -> dict[str, Any]:
    return {
        "conversation_id": row.conversation_id,
        "title": row.title,
        "knowledge_base_id": row.knowledge_base_id,
        "pipeline_config_id": row.pipeline_config_id,
        "updated_at": row.updated_at,
        "run_count": int(row.run_count or 0),
        "token_in": int(row.token_in or 0),
        "token_out": int(row.token_out or 0),
        "token_cached": int(row.token_cached or 0),
        "cost_micros": int(row.cost_micros) if row.cost_micros is not None else None,
        "last_run_at": row.last_run_at,
    }


def _experiment_row(row: Any) -> dict[str, Any]:
    return {
        "experiment_id": row.experiment_id,
        "experiment_name": row.experiment_name,
        "eval_run_count": int(row.eval_run_count or 0),
        "run_count": int(row.run_count or 0),
        "token_in": int(row.token_in or 0),
        "token_out": int(row.token_out or 0),
        "token_cached": int(row.token_cached or 0),
        "cost_micros": int(row.cost_micros) if row.cost_micros is not None else None,
        "last_run_at": row.last_run_at,
    }
