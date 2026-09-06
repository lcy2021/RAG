"""compare_specs, compare_variants, eval_experiments, eval_runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from db.entities import (
    CompareSpec,
    CompareVariant,
    EvalExperiment,
    EvalRun,
    EvalScore,
    EvalSummary,
    RagRun,
)
from db.serialize import as_dict
from models.enums import RunStatus
from repositories.base import persist, remove_by_pk


def _variant_dict(variant: CompareVariant) -> dict[str, Any]:
    return as_dict(variant)


def _spec_dict(spec: CompareSpec, variants: list[CompareVariant]) -> dict[str, Any]:
    data = as_dict(spec)
    data["variants"] = [_variant_dict(item) for item in variants]
    return data


def _experiment_dict(
    experiment: EvalExperiment,
    *,
    scenario_name: str | None = None,
    compare_spec_name: str | None = None,
    run_count: int = 0,
) -> dict[str, Any]:
    data = as_dict(experiment)
    data["scenario_name"] = scenario_name
    data["compare_spec_name"] = compare_spec_name
    data["run_count"] = run_count
    return data


class ExperimentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def insert_compare_spec(
        self,
        *,
        name: str,
        query_pipeline_id: UUID,
        description: str | None,
        definition: dict[str, Any],
        variants: list[dict[str, Any]],
    ) -> dict[str, Any]:
        spec = CompareSpec(
            name=name,
            query_pipeline_id=query_pipeline_id,
            description=description,
            definition=definition,
        )
        await persist(self._session, spec)
        for item in variants:
            self._session.add(
                CompareVariant(
                    compare_spec_id=spec.id,
                    label=item["label"],
                    ordinal=item["ordinal"],
                    query_pipeline_id=item.get("query_pipeline_id"),
                    ingest_pipeline_id=item.get("ingest_pipeline_id"),
                    vector_collection_id=item.get("vector_collection_id"),
                    slot_overrides=item.get("slot_overrides") or {},
                )
            )
        await self._session.flush()
        loaded = await self.get_compare_spec(spec.id)
        assert loaded is not None
        return loaded

    async def get_compare_spec(self, spec_id: UUID) -> dict[str, Any] | None:
        spec = await self._session.get(CompareSpec, spec_id)
        if spec is None:
            return None
        variants = await self._list_variants(spec_id)
        return _spec_dict(spec, variants)

    async def _list_variants(self, spec_id: UUID) -> list[CompareVariant]:
        result = await self._session.scalars(
            select(CompareVariant)
            .where(CompareVariant.compare_spec_id == spec_id)
            .order_by(CompareVariant.ordinal)
        )
        return list(result)

    async def insert_experiment(
        self,
        *,
        name: str,
        scenario_id: UUID,
        compare_spec_id: UUID,
        judge_binding_id: UUID | None,
        metric_plugins: list[str],
    ) -> dict[str, Any]:
        experiment = EvalExperiment(
            name=name,
            scenario_id=scenario_id,
            compare_spec_id=compare_spec_id,
            judge_binding_id=judge_binding_id,
            metric_plugins=metric_plugins,
        )
        await persist(self._session, experiment)
        return _experiment_dict(experiment, run_count=0)

    async def list_experiments(self) -> list[dict[str, Any]]:
        from db.entities import Scenario

        result = await self._session.execute(
            select(EvalExperiment, Scenario.name, CompareSpec.name)
            .join(Scenario, Scenario.id == EvalExperiment.scenario_id)
            .join(CompareSpec, CompareSpec.id == EvalExperiment.compare_spec_id)
            .order_by(EvalExperiment.name)
        )
        rows = []
        for experiment, scenario_name, spec_name in result.all():
            run_count = await self._run_count(experiment.id)
            rows.append(
                _experiment_dict(
                    experiment,
                    scenario_name=scenario_name,
                    compare_spec_name=spec_name,
                    run_count=run_count,
                )
            )
        return rows

    async def get_experiment(self, experiment_id: UUID) -> dict[str, Any] | None:
        from db.entities import Scenario

        result = await self._session.execute(
            select(EvalExperiment, Scenario.name, CompareSpec.name)
            .join(Scenario, Scenario.id == EvalExperiment.scenario_id)
            .join(CompareSpec, CompareSpec.id == EvalExperiment.compare_spec_id)
            .where(EvalExperiment.id == experiment_id)
        )
        row = result.first()
        if row is None:
            return None
        experiment, scenario_name, spec_name = row
        return _experiment_dict(
            experiment,
            scenario_name=scenario_name,
            compare_spec_name=spec_name,
            run_count=await self._run_count(experiment.id),
        )

    async def _run_count(self, experiment_id: UUID) -> int:
        result = await self._session.scalars(
            select(EvalRun).where(EvalRun.experiment_id == experiment_id)
        )
        return len(list(result))

    async def delete_experiment(self, experiment_id: UUID) -> bool:
        experiment = await self._session.get(EvalExperiment, experiment_id)
        if experiment is None:
            return False
        spec_id = experiment.compare_spec_id
        await self._session.delete(experiment)
        await self._session.flush()
        # Drop orphaned compare spec if nothing else references it.
        remaining = await self._session.scalars(
            select(EvalExperiment).where(EvalExperiment.compare_spec_id == spec_id)
        )
        if remaining.first() is None:
            await remove_by_pk(self._session, CompareSpec, spec_id)
        return True

    async def insert_eval_run(
        self,
        *,
        experiment_id: UUID,
        snapshot: dict[str, Any],
        corpus_fingerprint: str | None = None,
        status: str = "queued",
    ) -> dict[str, Any]:
        run = EvalRun(
            experiment_id=experiment_id,
            status=RunStatus(status),
            snapshot=snapshot,
            corpus_fingerprint=corpus_fingerprint,
        )
        return await persist(self._session, run)

    async def set_eval_run_status(self, run_id: UUID, status: str) -> None:
        run = await self._session.get(EvalRun, run_id)
        if run is None:
            return
        run.status = RunStatus(status)
        await self._session.flush()

    async def lock_eval_run(self, run_id: UUID) -> dict[str, Any] | None:
        """Load eval run with row lock for concurrent variant progress updates."""
        result = await self._session.execute(
            select(EvalRun).where(EvalRun.id == run_id).with_for_update()
        )
        run = result.scalar_one_or_none()
        return as_dict(run) if run else None

    async def patch_variant_progress(
        self,
        run_id: UUID,
        variant_id: UUID,
        patch: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update one variant's progress fields inside eval_runs.snapshot (locked)."""
        result = await self._session.execute(
            select(EvalRun).where(EvalRun.id == run_id).with_for_update()
        )
        run = result.scalar_one_or_none()
        if run is None:
            return None
        snapshot = dict(run.snapshot or {})
        variants = [dict(item) for item in (snapshot.get("variants") or [])]
        target = str(variant_id)
        found = False
        for item in variants:
            if str(item.get("id")) != target:
                continue
            found = True
            item.update(patch)
            break
        if not found:
            return as_dict(run)
        snapshot["variants"] = variants
        run.snapshot = snapshot
        flag_modified(run, "snapshot")
        await self._session.flush()
        return as_dict(run)

    async def list_eval_rag_latencies(self, eval_run_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.execute(
            select(
                RagRun.compare_variant_id,
                RagRun.latency_ms,
                RagRun.cost_micros,
                RagRun.status,
            ).where(RagRun.eval_run_id == eval_run_id)
        )
        return [
            {
                "compare_variant_id": row.compare_variant_id,
                "latency_ms": row.latency_ms,
                "cost_micros": row.cost_micros,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
            }
            for row in result.all()
        ]

    async def get_variant(self, variant_id: UUID) -> dict[str, Any] | None:
        variant = await self._session.get(CompareVariant, variant_id)
        return as_dict(variant) if variant else None

    async def insert_promotion(
        self,
        *,
        scenario_id: UUID,
        eval_run_id: UUID,
        compare_variant_id: UUID,
        knowledge_base_id: UUID,
        ingest_pipeline_id: UUID | None,
        query_pipeline_id: UUID | None,
        vector_collection_id: UUID | None,
    ) -> dict[str, Any]:
        from db.entities import PipelinePromotion

        return await persist(
            self._session,
            PipelinePromotion(
                scenario_id=scenario_id,
                eval_run_id=eval_run_id,
                compare_variant_id=compare_variant_id,
                knowledge_base_id=knowledge_base_id,
                ingest_pipeline_id=ingest_pipeline_id,
                query_pipeline_id=query_pipeline_id,
                vector_collection_id=vector_collection_id,
            ),
        )

    async def list_promotions_for_run(self, eval_run_id: UUID) -> list[dict[str, Any]]:
        from db.entities import PipelinePromotion

        result = await self._session.scalars(
            select(PipelinePromotion)
            .where(PipelinePromotion.eval_run_id == eval_run_id)
            .order_by(PipelinePromotion.created_at.desc())
        )
        return [as_dict(row) for row in result]

    async def finish_eval_run(
        self,
        run_id: UUID,
        *,
        status: str,
        winner_variant_id: UUID | None,
        error_message: str | None,
    ) -> None:
        run = await self._session.get(EvalRun, run_id)
        if run is None:
            return
        run.status = RunStatus(status)
        run.winner_variant_id = winner_variant_id
        run.error_message = error_message
        run.finished_at = datetime.now(UTC)
        await self._session.flush()

    async def get_eval_run(self, run_id: UUID) -> dict[str, Any] | None:
        run = await self._session.get(EvalRun, run_id)
        return as_dict(run) if run else None

    async def list_eval_runs(self, experiment_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(EvalRun)
            .where(EvalRun.experiment_id == experiment_id)
            .order_by(EvalRun.created_at.desc())
        )
        return [as_dict(row) for row in result]

    async def insert_score(
        self,
        *,
        eval_run_id: UUID,
        eval_item_id: UUID,
        compare_variant_id: UUID,
        rag_run_id: UUID | None,
        metric: str,
        value: float,
        detail: dict[str, Any],
    ) -> dict[str, Any]:
        return await persist(
            self._session,
            EvalScore(
                eval_run_id=eval_run_id,
                eval_item_id=eval_item_id,
                compare_variant_id=compare_variant_id,
                rag_run_id=rag_run_id,
                metric=metric,
                value=value,
                detail=detail,
            ),
        )

    async def list_scores(self, eval_run_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(EvalScore).where(EvalScore.eval_run_id == eval_run_id)
        )
        return [as_dict(row) for row in result]

    async def replace_summaries(
        self, eval_run_id: UUID, summaries: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        existing = await self._session.scalars(
            select(EvalSummary).where(EvalSummary.eval_run_id == eval_run_id)
        )
        for row in existing:
            await self._session.delete(row)
        await self._session.flush()
        out: list[dict[str, Any]] = []
        for item in summaries:
            out.append(
                await persist(
                    self._session,
                    EvalSummary(
                        eval_run_id=eval_run_id,
                        compare_variant_id=item["compare_variant_id"],
                        metrics=item.get("metrics") or {},
                        composite_score=item.get("composite_score"),
                        latency_p50_ms=item.get("latency_p50_ms"),
                        latency_p95_ms=item.get("latency_p95_ms"),
                        cost_micros_avg=item.get("cost_micros_avg"),
                        rank=item.get("rank"),
                        is_winner=bool(item.get("is_winner")),
                    ),
                )
            )
        return out

    async def list_summaries(self, eval_run_id: UUID) -> list[dict[str, Any]]:
        result = await self._session.scalars(
            select(EvalSummary)
            .where(EvalSummary.eval_run_id == eval_run_id)
            .order_by(EvalSummary.rank.nulls_last(), EvalSummary.compare_variant_id)
        )
        return [as_dict(row) for row in result]
