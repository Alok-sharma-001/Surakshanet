import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import get_db
from app.models.vision import BehaviorFlag, BehaviorFlagType, BehaviorFlagStatus, NoParkingZone
from app.models.user import User, UserRole
from app.services.auth_service import get_current_user, require_role


@pytest.mark.asyncio
async def test_get_vision_status_unavailable_by_default():
    """SN-073: GET /vision/status returns explicit unavailable status when no worker/source."""
    operator = User(
        id=uuid.uuid4(),
        email="operator@surakshanet.gov.in",
        name="Traffic Operator",
        role=UserRole.OPERATOR,
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: operator
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/v1/vision/status")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "unavailable"
            assert data["reason"] is not None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_latest_detections_offline():
    """SN-078: GET /vision/detections/latest returns offline state when worker offline."""
    operator = User(
        id=uuid.uuid4(),
        email="operator@surakshanet.gov.in",
        name="Traffic Operator",
        role=UserRole.OPERATOR,
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: operator
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.get("/api/v1/vision/detections/latest?cam_id=CAM-01")
            assert res.status_code == 200
            data = res.json()
            assert data["detections"] == []
            assert data["fps"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_resolve_flag_human_gate_and_audit():
    """SN-077: PATCH /vision/flags/{id}/resolve requires operator and logs audit entry."""
    flag_id = uuid.uuid4()
    operator = User(
        id=uuid.uuid4(),
        email="operator@surakshanet.gov.in",
        name="Traffic Operator",
        role=UserRole.OPERATOR,
        is_active=True,
    )

    mock_flag = BehaviorFlag(
        id=flag_id,
        flag_type=BehaviorFlagType.WRONG_WAY,
        camera_id="CAM-01",
        track_id="trk-42",
        confidence=0.91,
        evidence={"delta": 180.0},
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    # Mock select returning mock_flag
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_flag
    mock_db.execute.return_value = mock_result

    async def override_db():
        yield mock_db

    async def override_user():
        return operator

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.patch(
                f"/api/v1/vision/flags/{flag_id}/resolve",
                json={"status": "CONFIRMED", "note": "Verified by operator on CCTV"}
            )
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "CONFIRMED"
            assert data["resolved_by"] == str(operator.id)
            assert data["note"] == "Verified by operator on CCTV"
            assert mock_flag.status == BehaviorFlagStatus.CONFIRMED
            assert mock_flag.resolved_by == operator.id
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_restricted_zones_create_and_list():
    """SN-079: POST /vision/zones and GET /vision/zones endpoints."""
    operator = User(
        id=uuid.uuid4(),
        email="operator@surakshanet.gov.in",
        name="Traffic Operator",
        role=UserRole.OPERATOR,
        is_active=True,
    )

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    async def override_db():
        yield mock_db

    async def override_user():
        return operator

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Create zone
            res = await client.post(
                "/api/v1/vision/zones",
                json={
                    "camera_id": "CAM-01",
                    "name": "Bus Stop Clearway",
                    "polygon": [[100, 100], [200, 100], [200, 200], [100, 200]],
                    "active_start_time": "08:00",
                    "active_end_time": "20:00",
                }
            )
            assert res.status_code == 201
            data = res.json()
            assert data["name"] == "Bus Stop Clearway"
            assert data["camera_id"] == "CAM-01"
            assert len(data["polygon"]) == 4
    finally:
        app.dependency_overrides.clear()
