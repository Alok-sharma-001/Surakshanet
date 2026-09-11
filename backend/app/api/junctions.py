from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, List
from uuid import UUID

from app.database import get_db
from app.schemas.traffic import JunctionCreate, JunctionResponse, JunctionUpdate
from app.services.auth_service import require_role
from app.models.user import User
from app.services import traffic_service

router = APIRouter(prefix="/junctions", tags=["Junctions"])


@router.get("/nearby", response_model=List[JunctionResponse])
async def get_junctions_nearby(
    latitude: float = Query(..., description="Latitude coordinate", ge=-90.0, le=90.0),
    longitude: float = Query(..., description="Longitude coordinate", ge=-180.0, le=180.0),
    radius: float = Query(1000.0, description="Radius in meters", ge=0.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    """Retrieve junctions within a radius using PostGIS ST_DWithin."""
    return await traffic_service.get_junctions_within_radius(
        db, latitude=latitude, longitude=longitude, radius_meters=radius
    )


@router.get("/spatial/nearest", response_model=JunctionResponse)
async def get_nearest_junction(
    latitude: float = Query(..., description="Latitude coordinate"),
    longitude: float = Query(..., description="Longitude coordinate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    junction = await traffic_service.get_nearest_junction(db, latitude=latitude, longitude=longitude)
    if not junction:
        raise HTTPException(status_code=404, detail="No junctions found")
    return junction


@router.get("", response_model=List[JunctionResponse])
async def list_junctions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    return await traffic_service.get_junctions(db, skip=skip, limit=limit)


@router.get("/{id}", response_model=JunctionResponse)
async def get_junction(
    id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR", "EMERGENCY_SERVICES", "VIEWER"))
) -> Any:
    junction = await traffic_service.get_junction(db, junction_id=id)
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction


@router.post("", response_model=JunctionResponse, status_code=status.HTTP_201_CREATED)
async def create_junction(
    junction_in: JunctionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    return await traffic_service.create_junction(db, data=junction_in)


@router.patch("/{id}", response_model=JunctionResponse)
async def update_junction(
    id: UUID,
    junction_in: JunctionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("ADMIN", "OPERATOR"))
) -> Any:
    junction = await traffic_service.update_junction(db, junction_id=id, data=junction_in)
    if not junction:
        raise HTTPException(status_code=404, detail="Junction not found")
    return junction
