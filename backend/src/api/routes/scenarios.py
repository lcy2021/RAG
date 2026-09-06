from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile

from api.deps import scenario_service_dep
from models.schemas import (
    EvalItemCreate,
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
from services.scenarios import ScenarioService

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

ScenarioSvc = Annotated[ScenarioService, Depends(scenario_service_dep)]


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(svc: ScenarioSvc) -> list[ScenarioOut]:
    return await svc.list_scenarios()


@router.post("", response_model=ScenarioOut)
async def create_scenario(payload: ScenarioCreate, svc: ScenarioSvc) -> ScenarioOut:
    return await svc.create_scenario(payload)


@router.get("/{scenario_id}", response_model=ScenarioDetailOut)
async def get_scenario(scenario_id: UUID, svc: ScenarioSvc) -> ScenarioDetailOut:
    return await svc.get_scenario(scenario_id)


@router.put("/{scenario_id}", response_model=ScenarioOut)
async def update_scenario(
    scenario_id: UUID, payload: ScenarioUpdate, svc: ScenarioSvc
) -> ScenarioOut:
    return await svc.update_scenario(scenario_id, payload)


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: UUID, svc: ScenarioSvc) -> None:
    await svc.delete_scenario(scenario_id)


@router.get("/{scenario_id}/items", response_model=list[EvalItemOut])
async def list_items(scenario_id: UUID, svc: ScenarioSvc) -> list[EvalItemOut]:
    return await svc.list_items(scenario_id)


@router.post("/{scenario_id}/items", response_model=EvalItemOut)
async def create_item(
    scenario_id: UUID, payload: EvalItemCreate, svc: ScenarioSvc
) -> EvalItemOut:
    return await svc.create_item(scenario_id, payload)


@router.post("/{scenario_id}/items/import", response_model=ScenarioItemsImportResult)
async def import_items(
    scenario_id: UUID, payload: ScenarioItemsImport, svc: ScenarioSvc
) -> ScenarioItemsImportResult:
    return await svc.import_items(scenario_id, payload)


@router.post("/{scenario_id}/items/import-file", response_model=ScenarioItemsImportResult)
async def import_items_file(
    scenario_id: UUID,
    svc: ScenarioSvc,
    file: UploadFile = File(...),
    replace: bool = Form(False),
) -> ScenarioItemsImportResult:
    return await svc.import_items_file(scenario_id, file, replace=replace)


@router.put("/{scenario_id}/items/{item_id}", response_model=EvalItemOut)
async def update_item(
    scenario_id: UUID, item_id: UUID, payload: EvalItemUpdate, svc: ScenarioSvc
) -> EvalItemOut:
    return await svc.update_item(scenario_id, item_id, payload)


@router.delete("/{scenario_id}/items/{item_id}", status_code=204)
async def delete_item(scenario_id: UUID, item_id: UUID, svc: ScenarioSvc) -> None:
    await svc.delete_item(scenario_id, item_id)


@router.post("/{scenario_id}/items/{item_id}/spans", response_model=EvalItemSpanOut)
async def create_span(
    scenario_id: UUID,
    item_id: UUID,
    payload: EvalItemSpanCreate,
    svc: ScenarioSvc,
) -> EvalItemSpanOut:
    return await svc.create_span(scenario_id, item_id, payload)


@router.delete("/{scenario_id}/items/{item_id}/spans/{span_id}", status_code=204)
async def delete_span(
    scenario_id: UUID, item_id: UUID, span_id: UUID, svc: ScenarioSvc
) -> None:
    await svc.delete_span(scenario_id, item_id, span_id)
