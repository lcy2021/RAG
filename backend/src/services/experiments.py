"""Compare specs, eval runs, and scoring."""

from __future__ import annotations

import math
import statistics
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from configs.settings import Settings
from engine.citations import citation_spans, normalize_sources
from engine.runner import default_collection_id, ordered_calls, run_pipeline
from infra.models import LiteLLMClient
from jobs.eval_progress import discard_progress_lock, progress_lock
from models.enums import PipelineKind, PipelineStage
from models.schemas import (
    CompareVariantIn,
    EvalRunDetailOut,
    EvalRunOut,
    EvalScoreOut,
    EvalSummaryOut,
    EvalVariantProgressOut,
    ExperimentCreate,
    ExperimentOut,
    PromotionOut,
)
from plugins.context import MemoryTrace, PluginContext
from plugins.registry import PluginRegistry, get_registry
from repositories.chat import ChatRepository
from repositories.experiments import ExperimentRepository
from repositories.knowledge_bases import KnowledgeBaseRepository
from repositories.pipelines import PipelineRepository
from repositories.scenarios import ScenarioRepository
from repositories.settings import SettingsRepository
from services.bindings import BindingResolver
from services.knowledge_bases import first_slot_binding_id


class ExperimentService:
    def __init__(
        self,
        session: AsyncSession,
        settings: Settings,
        registry: PluginRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._session = session
        self._repo = ExperimentRepository(session)
        self._scenarios = ScenarioRepository(session)
        self._pipelines = PipelineRepository(session)
        self._kb = KnowledgeBaseRepository(session)
        self._chat = ChatRepository(session)
        self._resolver = BindingResolver(SettingsRepository(session))
        self._registry = registry or get_registry()

    async def list_experiments(self) -> list[ExperimentOut]:
        return [ExperimentOut.model_validate(row) for row in await self._repo.list_experiments()]

    async def get_experiment(self, experiment_id: UUID) -> ExperimentOut:
        row = await self._repo.get_experiment(experiment_id)
        if not row:
            raise HTTPException(status_code=404, detail="experiment not found")
        return ExperimentOut.model_validate(row)

    async def create_experiment(self, payload: ExperimentCreate) -> ExperimentOut:
        scenario = await self._scenarios.get(payload.scenario_id)
        if not scenario:
            raise HTTPException(status_code=400, detail="scenario not found")
        if len(payload.variants) < 2:
            raise HTTPException(
                status_code=400, detail="at least two query pipelines are required"
            )
        self._validate_variants(payload.variants)

        for item in payload.variants:
            if item.query_pipeline_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"variant '{item.label}' must reference a query pipeline",
                )
            pipeline = await self._pipelines.get(item.query_pipeline_id)
            if not pipeline or pipeline.get("kind") != PipelineKind.QUERY:
                raise HTTPException(
                    status_code=400,
                    detail=f"query pipeline not found for variant '{item.label}'",
                )

        anchor_pipeline_id = payload.variants[0].query_pipeline_id
        assert anchor_pipeline_id is not None

        metrics = list(payload.metric_plugins) if payload.metric_plugins else list(
            scenario["metric_plugins"]
        )
        if not metrics:
            raise HTTPException(status_code=400, detail="no metric plugins configured")
        self._validate_metric_plugins(metrics)

        labels = [item.label.strip() for item in payload.variants]
        if len(set(labels)) != len(labels):
            raise HTTPException(status_code=400, detail="variant labels must be unique")

        variant_rows = [
            {
                "label": item.label.strip(),
                "ordinal": index,
                "query_pipeline_id": item.query_pipeline_id,
                "vector_collection_id": item.vector_collection_id,
                "slot_overrides": {
                    stage: {"plugin": override.plugin, "params": override.params}
                    for stage, override in (item.slot_overrides or {}).items()
                },
            }
            for index, item in enumerate(payload.variants)
        ]
        spec_name = f"{payload.name} · spec · {uuid4().hex[:8]}"
        try:
            spec = await self._repo.insert_compare_spec(
                name=spec_name,
                query_pipeline_id=anchor_pipeline_id,
                description=payload.notes,
                definition={
                    "source": "experiment_create",
                    "mode": "pipeline_compare",
                },
                variants=variant_rows,
            )
            experiment = await self._repo.insert_experiment(
                name=payload.name,
                scenario_id=payload.scenario_id,
                compare_spec_id=spec["id"],
                judge_binding_id=payload.judge_binding_id,
                metric_plugins=metrics,
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="experiment name already exists") from exc

        loaded = await self._repo.get_experiment(experiment["id"])
        assert loaded is not None
        return ExperimentOut.model_validate(loaded)

    async def delete_experiment(self, experiment_id: UUID) -> None:
        try:
            deleted = await self._repo.delete_experiment(experiment_id)
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="experiment is still referenced") from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="experiment not found")

    async def list_runs(self, experiment_id: UUID) -> list[EvalRunOut]:
        await self._require_experiment(experiment_id)
        return [
            EvalRunOut.model_validate(row)
            for row in await self._repo.list_eval_runs(experiment_id)
        ]

    async def get_run(self, experiment_id: UUID, run_id: UUID) -> EvalRunDetailOut:
        await self._require_experiment(experiment_id)
        run = await self._repo.get_eval_run(run_id)
        if not run or run["experiment_id"] != experiment_id:
            raise HTTPException(status_code=404, detail="eval run not found")
        summaries = await self._repo.list_summaries(run_id)
        scores = await self._repo.list_scores(run_id)
        return EvalRunDetailOut(
            **EvalRunOut.model_validate(run).model_dump(),
            summaries=[EvalSummaryOut.model_validate(row) for row in summaries],
            scores=[EvalScoreOut.model_validate(row) for row in scores],
            variants=self._variant_progress_from_snapshot(run.get("snapshot") or {}),
        )

    async def enqueue_run(self, experiment_id: UUID) -> EvalRunDetailOut:
        """Validate inputs and create a queued eval run (one job per pipeline variant)."""
        await self._abandon_never_started_runs(experiment_id)
        experiment = await self._require_experiment(experiment_id)
        scenario_detail = await self._scenarios.get_detail(experiment["scenario_id"])
        if not scenario_detail:
            raise HTTPException(status_code=400, detail="scenario not found")
        items = scenario_detail.get("items") or []
        if not items:
            raise HTTPException(status_code=400, detail="scenario has no gold items")

        kb = await self._kb.get(scenario_detail["knowledge_base_id"])
        if not kb:
            raise HTTPException(status_code=400, detail="knowledge base not found")
        default_collection = default_collection_id(kb)
        if default_collection is None:
            raise HTTPException(
                status_code=400,
                detail="knowledge base has no vector collection; upload a document first",
            )

        spec = await self._repo.get_compare_spec(experiment["compare_spec_id"])
        if not spec or not spec.get("variants"):
            raise HTTPException(status_code=400, detail="compare spec has no variants")

        variant_snapshot: list[dict[str, Any]] = []
        for variant in spec["variants"]:
            pipeline_id = variant.get("query_pipeline_id") or spec["query_pipeline_id"]
            pipeline = await self._pipelines.get(pipeline_id)
            if not pipeline or pipeline.get("kind") != PipelineKind.QUERY:
                raise HTTPException(
                    status_code=400,
                    detail=f"query pipeline missing for variant {variant['label']}",
                )
            variant_snapshot.append(
                {
                    "id": str(variant["id"]),
                    "label": variant["label"],
                    "ordinal": variant["ordinal"],
                    "query_pipeline_id": str(pipeline_id) if pipeline_id else None,
                    "query_pipeline_name": pipeline.get("name"),
                    "status": "queued",
                    "done_items": 0,
                    "total_items": len(items),
                    "error_message": None,
                }
            )

        metrics = list(experiment.get("metric_plugins") or scenario_detail["metric_plugins"])
        if "faithfulness" in metrics:
            has_judge = bool(experiment.get("judge_binding_id") or kb.get("default_generator_binding_id"))
            if not has_judge:
                for variant in spec["variants"]:
                    pipeline_id = variant.get("query_pipeline_id") or spec["query_pipeline_id"]
                    pipeline = await self._pipelines.get(pipeline_id)
                    if pipeline and first_slot_binding_id(pipeline, PipelineStage.GENERATOR):
                        has_judge = True
                        break
            if not has_judge:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "faithfulness requires an LLM credential: set judge_binding_id "
                        "on the experiment, or binding_id on a query pipeline generator"
                    ),
                )
        weights = dict(scenario_detail.get("metric_weights") or {})
        for name in metrics:
            weights.setdefault(name, 1.0)

        run = await self._repo.insert_eval_run(
            experiment_id=experiment_id,
            status="queued",
            snapshot={
                "experiment_name": experiment["name"],
                "scenario_id": str(scenario_detail["id"]),
                "scenario_name": scenario_detail["name"],
                "knowledge_base_id": str(kb["id"]),
                "metrics": metrics,
                "metric_weights": weights,
                "variants": variant_snapshot,
                "item_count": len(items),
            },
        )
        return await self.get_run(experiment_id, run["id"])

    def list_queued_variant_ids(self, run: EvalRunDetailOut | dict[str, Any]) -> list[UUID]:
        """Variant IDs that should be scheduled as background jobs for this run."""
        if isinstance(run, EvalRunDetailOut):
            return [item.id for item in run.variants]
        snapshot = run.get("snapshot") or {}
        return [UUID(str(item["id"])) for item in (snapshot.get("variants") or [])]

    async def _write_variant_progress(
        self,
        run_id: UUID,
        variant_id: UUID,
        patch: dict[str, Any],
    ) -> None:
        """Serialize snapshot progress writes across parallel pipeline jobs."""
        lock = await progress_lock(run_id)
        async with lock:
            try:
                await self._repo.patch_variant_progress(run_id, variant_id, patch)
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                await self._repo.patch_variant_progress(run_id, variant_id, patch)
                await self._session.commit()

    async def execute_variant(
        self, experiment_id: UUID, run_id: UUID, variant_id: UUID
    ) -> None:
        """Execute gold items for one compare variant / query pipeline."""
        experiment = await self._require_experiment(experiment_id)
        run = await self._repo.get_eval_run(run_id)
        if not run or run["experiment_id"] != experiment_id:
            raise HTTPException(status_code=404, detail="eval run not found")
        if run["status"] not in {"queued", "running"}:
            return

        scenario_detail = await self._scenarios.get_detail(experiment["scenario_id"])
        if not scenario_detail:
            await self._write_variant_progress(
                run_id,
                variant_id,
                {"status": "failed", "error_message": "scenario not found"},
            )
            return
        items = scenario_detail.get("items") or []
        kb = await self._kb.get(scenario_detail["knowledge_base_id"])
        if not kb:
            await self._write_variant_progress(
                run_id,
                variant_id,
                {"status": "failed", "error_message": "knowledge base not found"},
            )
            return
        default_collection = default_collection_id(kb)
        if default_collection is None:
            await self._write_variant_progress(
                run_id,
                variant_id,
                {
                    "status": "failed",
                    "error_message": "knowledge base has no vector collection",
                },
            )
            return

        spec = await self._repo.get_compare_spec(experiment["compare_spec_id"])
        if not spec or not spec.get("variants"):
            await self._write_variant_progress(
                run_id,
                variant_id,
                {"status": "failed", "error_message": "compare spec has no variants"},
            )
            return

        variant = next((row for row in spec["variants"] if row["id"] == variant_id), None)
        if variant is None:
            await self._write_variant_progress(
                run_id,
                variant_id,
                {"status": "failed", "error_message": "variant not found"},
            )
            return

        metrics = list(experiment.get("metric_plugins") or scenario_detail["metric_plugins"])
        await self._repo.set_eval_run_status(run_id, "running")
        await self._write_variant_progress(
            run_id,
            variant_id,
            {"status": "running", "done_items": 0, "error_message": None},
        )

        pipeline_id = variant.get("query_pipeline_id") or spec["query_pipeline_id"]
        pipeline = await self._pipelines.get(pipeline_id)
        if not pipeline or pipeline.get("kind") != PipelineKind.QUERY:
            await self._write_variant_progress(
                run_id,
                variant_id,
                {
                    "status": "failed",
                    "error_message": f"query pipeline missing for variant {variant['label']}",
                },
            )
            return

        collection_id = variant.get("vector_collection_id") or default_collection
        overrides = variant.get("slot_overrides") or {}
        calls = ordered_calls(pipeline["slots"], PipelineKind.QUERY, slot_overrides=overrides)

        done_items = 0
        try:
            for item in items:
                gold_quotes = [
                    {"quote": span["quote"], "document_id": str(span["document_id"])}
                    for span in (item.get("spans") or [])
                ]
                rag_run = await self._chat.insert_eval_rag_run(
                    eval_run_id=run_id,
                    eval_item_id=item["id"],
                    compare_variant_id=variant["id"],
                    pipeline_config_id=pipeline_id,
                    knowledge_base_id=kb["id"],
                    vector_collection_id=collection_id,
                    variant_label=variant["label"],
                    slot_overrides=overrides,
                    resolved_params={},
                )
                data: dict[str, Any] = {
                    "query": item["question"],
                    "history": [],
                    "knowledge_base_id": kb["id"],
                    "vector_collection_id": collection_id,
                    "gold_quotes": gold_quotes,
                    "expected": item.get("expected"),
                }
                ctx = PluginContext(
                    resolver=self._resolver,
                    kb_repo=self._kb,
                    models=LiteLLMClient(),
                    trace=MemoryTrace(),
                    default_embedder_binding_id=kb.get("default_embedder_binding_id"),
                    default_generator_binding_id=(
                        experiment.get("judge_binding_id")
                        or kb.get("default_generator_binding_id")
                        or first_slot_binding_id(pipeline, PipelineStage.GENERATOR)
                    ),
                )
                started = time.perf_counter()
                try:
                    result = await run_pipeline(
                        calls=calls,
                        data=data,
                        ctx=ctx,
                        registry=self._registry,
                    )
                    answer = result.get("answer") or ""
                    latency = int((time.perf_counter() - started) * 1000)
                    await self._chat.finish_rag_run(
                        rag_run["id"],
                        status="succeeded",
                        answer_text=answer,
                        rewritten_query=result.get("rewritten_query"),
                        error_message=None,
                        latency_ms=latency,
                    )
                    await self._persist_retrieval(rag_run["id"], result, answer)
                    scored = await self._score_metrics(
                        result,
                        metrics=metrics,
                        judge_binding_id=experiment.get("judge_binding_id"),
                        ctx=ctx,
                    )
                    for metric, value in scored.items():
                        if value is None:
                            continue
                        await self._repo.insert_score(
                            eval_run_id=run_id,
                            eval_item_id=item["id"],
                            compare_variant_id=variant["id"],
                            rag_run_id=rag_run["id"],
                            metric=metric,
                            value=float(value),
                            detail={},
                        )
                except Exception as exc:
                    latency = int((time.perf_counter() - started) * 1000)
                    error_message = str(exc)
                    try:
                        await self._chat.finish_rag_run(
                            rag_run["id"],
                            status="failed",
                            answer_text=None,
                            rewritten_query=None,
                            error_message=error_message,
                            latency_ms=latency,
                        )
                        for span in ctx.trace.spans:
                            await self._chat.insert_stage_trace(
                                rag_run_id=rag_run["id"],
                                stage=span.stage,
                                plugin_name=span.plugin_name,
                                ordinal=span.ordinal,
                                output_json=span.output,
                                latency_ms=span.latency_ms,
                                error_message=span.error_message,
                            )
                        await self._session.commit()
                    except Exception:
                        await self._session.rollback()
                    await self._write_variant_progress(
                        run_id,
                        variant_id,
                        {
                            "status": "failed",
                            "done_items": done_items,
                            "error_message": error_message,
                        },
                    )
                    return

                for span in ctx.trace.spans:
                    await self._chat.insert_stage_trace(
                        rag_run_id=rag_run["id"],
                        stage=span.stage,
                        plugin_name=span.plugin_name,
                        ordinal=span.ordinal,
                        output_json=span.output,
                        latency_ms=span.latency_ms,
                        error_message=span.error_message,
                    )
                done_items += 1
                # Commit per-item artifacts before taking the shared progress lock.
                await self._session.commit()
                await self._write_variant_progress(
                    run_id,
                    variant_id,
                    {"status": "running", "done_items": done_items},
                )

            await self._write_variant_progress(
                run_id,
                variant_id,
                {
                    "status": "succeeded",
                    "done_items": done_items,
                    "error_message": None,
                },
            )
        except Exception as exc:
            await self._session.rollback()
            await self._write_variant_progress(
                run_id,
                variant_id,
                {
                    "status": "failed",
                    "done_items": done_items,
                    "error_message": str(exc),
                },
            )

    async def try_finalize_run(self, experiment_id: UUID, run_id: UUID) -> None:
        """When every pipeline variant is terminal, write summaries and finish the run."""
        lock = await progress_lock(run_id)
        async with lock:
            await self._try_finalize_run_locked(experiment_id, run_id)

    async def _try_finalize_run_locked(self, experiment_id: UUID, run_id: UUID) -> None:
        experiment = await self._require_experiment(experiment_id)
        run = await self._repo.lock_eval_run(run_id)
        if not run or run["experiment_id"] != experiment_id:
            return
        if run["status"] in {"succeeded", "failed"}:
            discard_progress_lock(run_id)
            return

        snapshot = dict(run.get("snapshot") or {})
        variants = list(snapshot.get("variants") or [])
        if not variants:
            await self._repo.finish_eval_run(
                run_id,
                status="failed",
                winner_variant_id=None,
                error_message="no variants in snapshot",
            )
            discard_progress_lock(run_id)
            return

        terminal = {"succeeded", "failed"}
        if any(str(item.get("status")) not in terminal for item in variants):
            return

        scenario_detail = await self._scenarios.get_detail(experiment["scenario_id"])
        metrics = list(
            experiment.get("metric_plugins")
            or (scenario_detail or {}).get("metric_plugins")
            or snapshot.get("metrics")
            or []
        )
        weights = dict(
            (scenario_detail or {}).get("metric_weights")
            or snapshot.get("metric_weights")
            or {}
        )
        for name in metrics:
            weights.setdefault(name, 1.0)

        scores = await self._repo.list_scores(run_id)
        latencies_rows = await self._repo.list_eval_rag_latencies(run_id)
        metric_values: dict[UUID, dict[str, list[float]]] = {
            UUID(str(item["id"])): {m: [] for m in metrics} for item in variants
        }
        latencies: dict[UUID, list[int]] = {
            UUID(str(item["id"])): [] for item in variants
        }
        for score in scores:
            vid = score["compare_variant_id"]
            if vid not in metric_values:
                continue
            metric = score["metric"]
            if metric in metric_values[vid]:
                metric_values[vid][metric].append(float(score["value"]))
        for row in latencies_rows:
            vid = row.get("compare_variant_id")
            if vid is None or vid not in latencies:
                continue
            if row.get("status") != "succeeded" or row.get("latency_ms") is None:
                continue
            latencies[vid].append(int(row["latency_ms"]))

        summary_variants = [
            {"id": UUID(str(item["id"])), "label": item.get("label") or str(item["id"])}
            for item in variants
            if str(item.get("status")) == "succeeded"
        ]
        summaries = self._build_summaries(
            variants=summary_variants,
            metrics=metrics,
            weights=weights,
            metric_values=metric_values,
            latencies=latencies,
            latency_p95_max=(scenario_detail or {}).get("latency_p95_ms_max"),
        )
        await self._repo.replace_summaries(run_id, summaries)

        failed = [item for item in variants if str(item.get("status")) == "failed"]
        if not summary_variants:
            errors = "; ".join(
                f"{item.get('label')}: {item.get('error_message') or 'failed'}"
                for item in failed
            ) or "all pipeline variants failed"
            await self._repo.finish_eval_run(
                run_id,
                status="failed",
                winner_variant_id=None,
                error_message=errors,
            )
            discard_progress_lock(run_id)
            return

        winner = next((row for row in summaries if row.get("is_winner")), None)
        warning = None
        if failed:
            warning = "; ".join(
                f"{item.get('label')}: {item.get('error_message') or 'failed'}"
                for item in failed
            )
        await self._repo.finish_eval_run(
            run_id,
            status="succeeded",
            winner_variant_id=winner["compare_variant_id"] if winner else None,
            error_message=warning,
        )
        discard_progress_lock(run_id)

    async def mark_variant_crashed(self, run_id: UUID, variant_id: UUID) -> None:
        """Mark a variant failed after an unexpected worker crash."""
        await self._write_variant_progress(
            run_id,
            variant_id,
            {"status": "failed", "error_message": "variant job crashed"},
        )

    async def _abandon_never_started_runs(self, experiment_id: UUID) -> None:
        """Fail runs that stayed queued with 0 progress (e.g. background job race)."""
        for run in await self._repo.list_eval_runs(experiment_id):
            if run["status"] not in {"queued", "running"}:
                continue
            variants = list((run.get("snapshot") or {}).get("variants") or [])
            if not variants:
                continue
            never_started = all(
                str(item.get("status") or "") == "queued"
                and int(item.get("done_items") or 0) == 0
                for item in variants
            )
            if not never_started:
                continue
            for item in variants:
                await self._write_variant_progress(
                    run["id"],
                    UUID(str(item["id"])),
                    {
                        "status": "failed",
                        "error_message": "abandoned: eval never started (retry)",
                    },
                )
            await self._repo.finish_eval_run(
                run["id"],
                status="failed",
                winner_variant_id=None,
                error_message="abandoned: eval never started (retry)",
            )
            await self._session.commit()
            discard_progress_lock(run["id"])

    @staticmethod
    def _variant_progress_from_snapshot(
        snapshot: dict[str, Any],
    ) -> list[EvalVariantProgressOut]:
        rows: list[EvalVariantProgressOut] = []
        for item in snapshot.get("variants") or []:
            try:
                rows.append(
                    EvalVariantProgressOut(
                        id=UUID(str(item["id"])),
                        label=str(item.get("label") or item["id"]),
                        ordinal=int(item.get("ordinal") or 0),
                        query_pipeline_id=(
                            UUID(str(item["query_pipeline_id"]))
                            if item.get("query_pipeline_id")
                            else None
                        ),
                        query_pipeline_name=item.get("query_pipeline_name"),
                        status=str(item.get("status") or "queued"),
                        done_items=int(item.get("done_items") or 0),
                        total_items=int(item.get("total_items") or 0),
                        error_message=item.get("error_message"),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        rows.sort(key=lambda row: row.ordinal)
        return rows

    async def promote(
        self,
        experiment_id: UUID,
        run_id: UUID,
        *,
        compare_variant_id: UUID | None = None,
    ) -> PromotionOut:
        experiment = await self._require_experiment(experiment_id)
        run = await self._repo.get_eval_run(run_id)
        if not run or run["experiment_id"] != experiment_id:
            raise HTTPException(status_code=404, detail="eval run not found")
        if run["status"] != "succeeded":
            raise HTTPException(status_code=400, detail="only succeeded runs can be promoted")

        variant_id = compare_variant_id or run.get("winner_variant_id")
        if not variant_id:
            raise HTTPException(status_code=400, detail="no winner variant to promote")
        variant = await self._repo.get_variant(variant_id)
        if not variant or variant["compare_spec_id"] != experiment["compare_spec_id"]:
            raise HTTPException(status_code=400, detail="variant does not belong to this experiment")

        scenario = await self._scenarios.get(experiment["scenario_id"])
        if not scenario:
            raise HTTPException(status_code=400, detail="scenario not found")
        kb = await self._kb.get(scenario["knowledge_base_id"])
        if not kb:
            raise HTTPException(status_code=400, detail="knowledge base not found")

        spec = await self._repo.get_compare_spec(experiment["compare_spec_id"])
        assert spec is not None
        baseline_pipeline_id = variant.get("query_pipeline_id") or spec["query_pipeline_id"]
        baseline = await self._pipelines.get(baseline_pipeline_id)
        if not baseline or baseline.get("kind") != PipelineKind.QUERY:
            raise HTTPException(status_code=400, detail="query pipeline not found")

        overrides = variant.get("slot_overrides") or {}
        # Pipeline-compare experiments already point at a full query pipeline; reuse it.
        if overrides:
            baked_slots = self._bake_slots(baseline["slots"], overrides)
            pipeline_name = (
                f"{experiment['name']} · {variant['label']} · promoted · {uuid4().hex[:6]}"
            )
            try:
                promoted_pipeline = await self._pipelines.insert(
                    name=pipeline_name,
                    kind=PipelineKind.QUERY.value,
                    description=(
                        f"Promoted from experiment '{experiment['name']}' "
                        f"variant '{variant['label']}' (eval run {run_id})"
                    ),
                    definition={
                        "promoted_from_eval_run_id": str(run_id),
                        "compare_variant_id": str(variant_id),
                        "source_pipeline_id": str(baseline_pipeline_id),
                    },
                    slots=baked_slots,
                )
            except IntegrityError as exc:
                raise HTTPException(
                    status_code=409, detail="promoted pipeline name conflict"
                ) from exc
        else:
            promoted_pipeline = baseline

        ingest_pipeline_id = variant.get("ingest_pipeline_id") or kb.get("ingest_pipeline_id")
        collection_id = variant.get("vector_collection_id")
        if collection_id is not None:
            collection = await self._kb.get_collection(collection_id)
            if not collection or collection["knowledge_base_id"] != kb["id"]:
                raise HTTPException(
                    status_code=400,
                    detail="variant collection does not belong to the scenario knowledge base",
                )
            await self._kb.set_default_collection(kb["id"], collection_id)

        await self._kb.apply_promotion(
            kb["id"],
            ingest_pipeline_id=ingest_pipeline_id,
            query_pipeline_id=promoted_pipeline["id"],
            promoted_from_eval_run_id=run_id,
        )
        row = await self._repo.insert_promotion(
            scenario_id=scenario["id"],
            eval_run_id=run_id,
            compare_variant_id=variant_id,
            knowledge_base_id=kb["id"],
            ingest_pipeline_id=ingest_pipeline_id,
            query_pipeline_id=promoted_pipeline["id"],
            vector_collection_id=collection_id or default_collection_id(kb),
        )
        return PromotionOut.model_validate(
            {
                **row,
                "variant_label": variant["label"],
                "query_pipeline_name": promoted_pipeline["name"],
            }
        )

    @staticmethod
    def _bake_slots(
        slots: list[dict[str, Any]], overrides: dict[str, Any]
    ) -> list[dict[str, Any]]:
        baked: list[dict[str, Any]] = []
        for index, slot in enumerate(slots):
            stage = str(slot["stage"])
            override = overrides.get(stage)
            if override:
                baked.append(
                    {
                        "stage": stage,
                        "mode": "first",
                        "ordinal": slot.get("ordinal", index),
                        "bindings": [
                            {
                                "name": override["plugin"],
                                "params": override.get("params") or {},
                            }
                        ],
                    }
                )
                continue
            baked.append(
                {
                    "stage": stage,
                    "mode": slot.get("mode") or "first",
                    "ordinal": slot.get("ordinal", index),
                    "bindings": list(slot.get("bindings") or []),
                }
            )
        return baked

    async def _persist_retrieval(
        self, rag_run_id: UUID, result: dict[str, Any], answer: str
    ) -> None:
        retrieved = list(result.get("retrieved") or [])
        sources_payload = normalize_sources(retrieved, answer=answer)
        rank_to_retrieved_id: dict[int, UUID] = {}
        for item in sources_payload:
            row = await self._chat.insert_retrieved_chunk(
                rag_run_id=rag_run_id,
                chunk_id=item.get("chunk_id"),
                retriever=str(item.get("retriever") or "dense"),
                rank=int(item.get("rank") or 0),
                score=item.get("score"),
                content_snapshot=str(item.get("content") or ""),
            )
            rank_to_retrieved_id[int(row["rank"])] = row["id"]
        for span in citation_spans(answer):
            rank = int(span["rank"])
            await self._chat.insert_citation(
                rag_run_id=rag_run_id,
                retrieved_id=rank_to_retrieved_id.get(rank),
                char_start=span.get("char_start"),
                char_end=span.get("char_end"),
                quote=span.get("quote"),
            )

    async def _score_metrics(
        self,
        result: dict[str, Any],
        *,
        metrics: list[str],
        judge_binding_id: UUID | None,
        ctx: PluginContext,
    ) -> dict[str, float | None]:
        data = dict(result)
        data.setdefault("metrics", {})
        out: dict[str, float | None] = {}
        for name in metrics:
            plugin = self._registry.get(PipelineStage.EVALUATOR, name)
            if plugin is None:
                raise HTTPException(status_code=400, detail=f"unknown evaluator plugin: {name}")
            params: dict[str, Any] = {}
            if name == "faithfulness":
                binding = judge_binding_id or ctx.default_generator_binding_id
                if binding is None:
                    raise ValueError(
                        "faithfulness requires an LLM credential: set judge_binding_id "
                        "on the experiment, or binding_id on the query pipeline generator"
                    )
                params["binding_id"] = str(binding)
            data = await plugin.execute(data, params, ctx)
            value = (data.get("metrics") or {}).get(name)
            out[name] = float(value) if value is not None else None
        return out

    @staticmethod
    def _build_summaries(
        *,
        variants: list[dict[str, Any]],
        metrics: list[str],
        weights: dict[str, float],
        metric_values: dict[UUID, dict[str, list[float]]],
        latencies: dict[UUID, list[int]],
        latency_p95_max: int | None,
    ) -> list[dict[str, Any]]:
        weight_sum = sum(float(weights.get(m, 1.0)) for m in metrics) or 1.0
        rows: list[dict[str, Any]] = []
        for variant in variants:
            vid = variant["id"]
            metric_avgs: dict[str, float] = {}
            for metric in metrics:
                values = metric_values[vid].get(metric) or []
                if values:
                    metric_avgs[metric] = sum(values) / len(values)
            composite = (
                sum(metric_avgs.get(m, 0.0) * float(weights.get(m, 1.0)) for m in metrics)
                / weight_sum
                if metric_avgs
                else None
            )
            lags = latencies.get(vid) or []
            p50 = int(statistics.median(lags)) if lags else None
            if not lags:
                p95 = None
            elif len(lags) == 1:
                p95 = lags[0]
            else:
                sorted_lags = sorted(lags)
                index = max(0, min(len(sorted_lags) - 1, int(math.ceil(0.95 * len(sorted_lags)) - 1)))
                p95 = int(sorted_lags[index])
            eligible = True
            if latency_p95_max is not None and p95 is not None and p95 > latency_p95_max:
                eligible = False
            rows.append(
                {
                    "compare_variant_id": vid,
                    "label": variant["label"],
                    "metrics": metric_avgs,
                    "composite_score": composite if eligible else None,
                    "latency_p50_ms": p50,
                    "latency_p95_ms": p95,
                    "cost_micros_avg": None,
                    "eligible": eligible,
                }
            )
        ranked = sorted(
            rows,
            key=lambda row: (
                0 if row["composite_score"] is not None else 1,
                -(row["composite_score"] or 0.0),
            ),
        )
        out: list[dict[str, Any]] = []
        for index, row in enumerate(ranked, start=1):
            out.append(
                {
                    "compare_variant_id": row["compare_variant_id"],
                    "metrics": row["metrics"],
                    "composite_score": row["composite_score"],
                    "latency_p50_ms": row["latency_p50_ms"],
                    "latency_p95_ms": row["latency_p95_ms"],
                    "cost_micros_avg": None,
                    "rank": index,
                    "is_winner": index == 1 and row["composite_score"] is not None,
                }
            )
        return out

    def _validate_variants(self, variants: list[CompareVariantIn]) -> None:
        for variant in variants:
            for stage, override in (variant.slot_overrides or {}).items():
                try:
                    PipelineStage(stage)
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=f"unknown stage: {stage}") from exc
                plugin = self._registry.get(stage, override.plugin)
                if plugin is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"unknown plugin {stage}/{override.plugin}",
                    )

    def _validate_metric_plugins(self, metrics: list[str]) -> None:
        known = {plugin.name for plugin in self._registry.list_stage(PipelineStage.EVALUATOR)}
        for name in metrics:
            if name not in known:
                raise HTTPException(status_code=400, detail=f"unknown evaluator plugin: {name}")

    async def _require_experiment(self, experiment_id: UUID) -> dict[str, Any]:
        row = await self._repo.get_experiment(experiment_id)
        if not row:
            raise HTTPException(status_code=404, detail="experiment not found")
        return row
