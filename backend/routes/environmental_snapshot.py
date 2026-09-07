from fastapi import APIRouter, HTTPException

from backend.schemas.environmental import EnvironmentalSnapshot
from backend.services.environmental_data_service import EnvironmentalDataService

router = APIRouter()
service = EnvironmentalDataService()


@router.get("/{region_id}", response_model=EnvironmentalSnapshot)
def get_environmental_snapshot(region_id: str):
    try:
        return service.get_environmental_snapshot(region_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
