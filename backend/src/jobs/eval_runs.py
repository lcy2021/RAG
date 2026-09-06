"""Background jobs for offline eval runs."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from fastapi import HTTPException

from configs.settings import get_settings
from db.session import get_sessionmaker
from services.experiments import ExperimentService

logger = logging.getLogger(__name__)

# FastAPI may schedule BackgroundTasks before the request session commits.
_RUN_VISIBLE_ATTEMPTS = 10
_RUN_VISIBLE_DELAY_S = 0.2


async def execute_eval_variant_job(
    experiment_id: UUID, run_id: UUID, variant_id: UUID
) -> None:
    """Run one pipeline variant after the enqueue request commits."""
    settings = get_settings()
    factory = get_sessionmaker()
    async with factory() as session:
        service = ExperimentService(session, settings)
        try:
            await _wait_for_eval_run(service, experiment_id, run_id)
            await service.execute_variant(experiment_id, run_id, variant_id)
            await session.commit()
            await service.try_finalize_run(experiment_id, run_id)
            await session.commit()
        except Exception:
            logger.exception(
                "eval run %s variant %s crashed", run_id, variant_id
            )
            await session.rollback()
            try:
                async with factory() as recover:
                    recover_svc = ExperimentService(recover, settings)
                    await _wait_for_eval_run(recover_svc, experiment_id, run_id)
                    await recover_svc.mark_variant_crashed(run_id, variant_id)
                    await recover_svc.try_finalize_run(experiment_id, run_id)
                    await recover.commit()
            except Exception:
                logger.exception(
                    "failed to mark eval run %s variant %s as failed",
                    run_id,
                    variant_id,
                )
            raise


async def _wait_for_eval_run(
    service: ExperimentService, experiment_id: UUID, run_id: UUID
) -> None:
    """Poll until the queued eval run is visible in this session."""
    last_exc: Exception | None = None
    for attempt in range(_RUN_VISIBLE_ATTEMPTS):
        try:
            await service.get_run(experiment_id, run_id)
            return
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
            last_exc = exc
            await asyncio.sleep(_RUN_VISIBLE_DELAY_S * (attempt + 1))
    if last_exc is not None:
        raise last_exc
    raise HTTPException(status_code=404, detail="eval run not found")


async def execute_eval_run_jobs(
    experiment_id: UUID, run_id: UUID, variant_ids: list[UUID]
) -> None:
    """Run query pipeline variants in parallel; progress writes are lock-serialized."""
    results = await asyncio.gather(
        *(
            execute_eval_variant_job(experiment_id, run_id, variant_id)
            for variant_id in variant_ids
        ),
        return_exceptions=True,
    )
    for variant_id, result in zip(variant_ids, results, strict=True):
        if isinstance(result, Exception):
            logger.error(
                "eval run %s variant %s failed: %s",
                run_id,
                variant_id,
                result,
                exc_info=result,
            )
