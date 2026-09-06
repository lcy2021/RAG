from fastapi import APIRouter

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/yaml")
async def import_yaml() -> dict:
    return {"status": "not_implemented"}
