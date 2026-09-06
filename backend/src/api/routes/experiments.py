from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends

from api.deps import SessionDep, experiment_service_dep
from jobs.eval_runs import execute_eval_run_jobs
from models.schemas import (
    EvalRunDetailOut,
    EvalRunOut,
    ExperimentCreate,
    ExperimentOut,
    PromoteRequest,
    PromotionOut,
)
from services.experiments import ExperimentService

router = APIRouter(prefix="/experiments", tags=["experiments"])

ExperimentSvc = Annotated[ExperimentService, Depends(experiment_service_dep)]


@router.get("", response_model=list[ExperimentOut])
async def list_experiments(svc: ExperimentSvc) -> list[ExperimentOut]:
    return await svc.list_experiments()


@router.post("", response_model=ExperimentOut)
async def create_experiment(payload: ExperimentCreate, svc: ExperimentSvc) -> ExperimentOut:
    return await svc.create_experiment(payload)


@router.get("/{experiment_id}", response_model=ExperimentOut)
async def get_experiment(experiment_id: UUID, svc: ExperimentSvc) -> ExperimentOut:
    return await svc.get_experiment(experiment_id)


@router.delete("/{experiment_id}", status_code=204)
async def delete_experiment(experiment_id: UUID, svc: ExperimentSvc) -> None:
    await svc.delete_experiment(experiment_id)


@router.get("/{experiment_id}/runs", response_model=list[EvalRunOut])
async def list_runs(experiment_id: UUID, svc: ExperimentSvc) -> list[EvalRunOut]:
    return await svc.list_runs(experiment_id)


@router.post("/{experiment_id}/runs", response_model=EvalRunDetailOut)
async def start_run(
    experiment_id: UUID,
    svc: ExperimentSvc,
    session: SessionDep,
    background_tasks: BackgroundTasks,
) -> EvalRunDetailOut:
    run = await svc.enqueue_run(experiment_id)
    variant_ids = svc.list_queued_variant_ids(run)
    # BackgroundTasks may start before the request dependency commits; flush first.
    await session.commit()
    background_tasks.add_task(
        execute_eval_run_jobs, experiment_id, run.id, variant_ids
    )
    return run


@router.get("/{experiment_id}/runs/{run_id}", response_model=EvalRunDetailOut)
async def get_run(experiment_id: UUID, run_id: UUID, svc: ExperimentSvc) -> EvalRunDetailOut:
    return await svc.get_run(experiment_id, run_id)


@router.post("/{experiment_id}/runs/{run_id}/promote", response_model=PromotionOut)
async def promote_run(
    experiment_id: UUID,
    run_id: UUID,
    svc: ExperimentSvc,
    payload: PromoteRequest | None = None,
) -> PromotionOut:
    body = payload or PromoteRequest()
    return await svc.promote(
        experiment_id,
        run_id,
        compare_variant_id=body.compare_variant_id,
    )
