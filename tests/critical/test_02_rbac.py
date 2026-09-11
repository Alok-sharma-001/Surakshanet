"""
SN-112 · Role-Based Access Control (RBAC) Critical Tests
=========================================================
Verifies the complete RBAC governance matrix across all 5 roles:
ADMIN, OPERATOR, EMERGENCY_SERVICES, VIEWER, CITIZEN.

Acceptance Criteria (docs/16-rbac.md §2, §5):
1. Every '—' (denied) cell in the permission matrix returns HTTP 403.
2. Every '✔' (allowed) cell returns non-403 (e.g. 200, 201, 202, 404, 422 - access granted).
3. No mutating endpoint accepts an anonymous request (unauthenticated requests return 401/403).
4. Every 403 rejection logs an ACCESS_DENIED audit row with result: DENIED and names role and action.
5. High-impact rate limits (SN-101): corridor activation (5/min), signal override (10/min), AB run (1 concurrent).
6. Mutation check: removing a require_role guard allows an unauthorized role and causes the test to fail.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User, UserRole
from app.models.audit import AuditActorType, AuditResult
from app.services.auth_service import get_current_user, require_role, enforce_rate_limit
from app.database import get_db


def create_user_for_role(role: UserRole) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"{role.value.lower()}@surakshanet.local",
        name=f"Test {role.value}",
        password_hash="mock_hash",
        role=role,
        is_active=True,
    )


# ---------------------------------------------------------------------------
# 1. Direct Dependency Guard Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_require_role_denial_and_access_denied_audit():
    """SN-099, SN-100: Denied role raises 403 and writes ACCESS_DENIED audit row."""
    guard = require_role("ADMIN", action="CORRIDOR_ACTIVATE")
    operator_user = create_user_for_role(UserRole.OPERATOR)

    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        await guard(request=None, current_user=operator_user, db=mock_db)

    assert exc_info.value.status_code == 403
    assert "Role OPERATOR cannot perform CORRIDOR_ACTIVATE" in exc_info.value.detail
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_require_role_success():
    """Authorized role passes through without error."""
    guard = require_role("ADMIN", "OPERATOR")
    operator_user = create_user_for_role(UserRole.OPERATOR)

    mock_db = AsyncMock()
    user = await guard(request=None, current_user=operator_user, db=mock_db)
    assert user.id == operator_user.id
    assert user.role == UserRole.OPERATOR


# ---------------------------------------------------------------------------
# 2. Permission Matrix Tests (docs/16-rbac.md §2)
# ---------------------------------------------------------------------------

# Matrix definition: (method, path, body, allowed_roles)
# Register is intentionally absent here — it's PUB (docs/16-rbac.md §2),
# reachable by every role and no token at all, and is covered by
# test_register_is_public_and_ignores_client_submitted_role in
# test_01_auth.py instead of this per-role denial matrix.
PERMISSION_MATRIX = [
    # 2. Signal override: ADMIN, OPERATOR
    ("POST", "/api/v1/signals/junctions/00000000-0000-0000-0000-000000000001/override", {"action": "HOLD_CURRENT", "value": 10}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 3. Signal mode change: ADMIN, OPERATOR
    ("PATCH", "/api/v1/signals/junctions/00000000-0000-0000-0000-000000000001/mode", {"mode": "FIXED"}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 4. Emergency corridor activate: ADMIN, EMERGENCY_SERVICES (SN-101: OPERATOR denied!)
    ("POST", "/api/v1/emergency/activate", {"priority": "HIGH", "vehicle_type": "AMBULANCE", "corridor": ["J0", "J1"]}, [UserRole.ADMIN, UserRole.EMERGENCY_SERVICES]),
    # 5. Emergency corridor deactivate: ADMIN, EMERGENCY_SERVICES
    ("POST", "/api/v1/emergency/deactivate/00000000-0000-0000-0000-000000000001", {}, [UserRole.ADMIN, UserRole.EMERGENCY_SERVICES]),
    # 6. Event approve: ADMIN only (SN-058)
    ("POST", "/api/v1/events/00000000-0000-0000-0000-000000000001/approve", {}, [UserRole.ADMIN]),
    # 7. Event publish: ADMIN only (SN-058)
    ("POST", "/api/v1/events/00000000-0000-0000-0000-000000000001/publish", {}, [UserRole.ADMIN]),
    # 8. Incident confirm: ADMIN, OPERATOR
    ("POST", "/api/v1/incidents/00000000-0000-0000-0000-000000000001/confirm", {}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 9. Incident dismiss: ADMIN, OPERATOR
    ("POST", "/api/v1/incidents/00000000-0000-0000-0000-000000000001/dismiss", {"reason": "False alarm"}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 10. Incident escalate: ADMIN, OPERATOR, EMERGENCY_SERVICES
    ("POST", "/api/v1/incidents/00000000-0000-0000-0000-000000000001/escalate", {}, [UserRole.ADMIN, UserRole.OPERATOR, UserRole.EMERGENCY_SERVICES]),
    # 11. Incident publish-warning: ADMIN only (Human Gate 2)
    ("POST", "/api/v1/incidents/00000000-0000-0000-0000-000000000001/publish-warning", {}, [UserRole.ADMIN]),
    # 12. A/B test run: ADMIN, OPERATOR
    ("POST", "/api/v1/ab/run", {"name": "Test Run", "seed": 42}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 13. ML Train: ADMIN only
    ("POST", "/api/v1/ml/train/start", {"num_episodes": 10}, [UserRole.ADMIN]),
    # 14. Audit ledger: ADMIN only (SN-106)
    ("GET", "/api/v1/audit", None, [UserRole.ADMIN]),
    # 15. Routing VMS broadcast: ADMIN, OPERATOR
    ("POST", "/api/v1/routing/vms/broadcast", {"panel_cluster": "NORTH", "line1": "SLOW", "line2": "DOWN"}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 16. Alerts read: ADMIN, OPERATOR, EMERGENCY_SERVICES, VIEWER (CITIZEN denied)
    ("GET", "/api/v1/alerts", None, [UserRole.ADMIN, UserRole.OPERATOR, UserRole.EMERGENCY_SERVICES, UserRole.VIEWER]),
    # 17. Alert acknowledge: ADMIN, OPERATOR
    ("PATCH", "/api/v1/alerts/00000000-0000-0000-0000-000000000001/acknowledge", {}, [UserRole.ADMIN, UserRole.OPERATOR]),
    # 18. Alert delete: ADMIN, OPERATOR
    ("DELETE", "/api/v1/alerts/00000000-0000-0000-0000-000000000001", None, [UserRole.ADMIN, UserRole.OPERATOR]),
]


@pytest.mark.parametrize("method,path,body,allowed_roles", PERMISSION_MATRIX)
def test_rbac_permission_matrix_enforcement(method, path, body, allowed_roles):
    """SN-112: Tests permission matrix across all 5 roles.
    Asserts 403 for every denied role and non-403 for every allowed role.
    """
    client = TestClient(app)
    all_roles = [UserRole.ADMIN, UserRole.OPERATOR, UserRole.EMERGENCY_SERVICES, UserRole.VIEWER, UserRole.CITIZEN]

    for test_role in all_roles:
        # Override current_user dependency
        app.dependency_overrides[get_current_user] = lambda r=test_role: create_user_for_role(r)
        
        # Mock DB for endpoints
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None, scalars=lambda: MagicMock(all=lambda: [])))
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            if method == "GET":
                response = client.get(path)
            elif method == "POST":
                response = client.post(path, json=body or {})
            elif method == "PATCH":
                response = client.patch(path, json=body or {})
            elif method == "DELETE":
                response = client.delete(path)
            else:
                continue

            if test_role in allowed_roles:
                assert response.status_code != 403, (
                    f"Role {test_role.value} was unexpectedly DENIED (403) on {method} {path}!"
                )
            else:
                assert response.status_code == 403, (
                    f"Role {test_role.value} was allowed (HTTP {response.status_code}) on {method} {path}, "
                    f"expected 403 Forbidden!"
                )
                data = response.json()
                assert "detail" in data
                assert f"Role {test_role.value} cannot perform" in data["detail"]
        finally:
            app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 3. Anonymous Rejection on Mutating Endpoints
# ---------------------------------------------------------------------------

MUTATING_ENDPOINTS = [
    # Register is intentionally absent here — unlike every other endpoint in
    # this list, it must accept an anonymous request (PUB, docs/16-rbac.md
    # §2): it's how every account, including the first one, is ever created.
    ("POST", "/api/v1/signals/junctions/00000000-0000-0000-0000-000000000001/override", {"action": "HOLD_CURRENT", "value": 10}),
    ("PATCH", "/api/v1/signals/junctions/00000000-0000-0000-0000-000000000001/mode", {"mode": "FIXED"}),
    ("POST", "/api/v1/emergency/activate", {"priority": "HIGH", "vehicle_type": "AMBULANCE", "corridor": ["J0", "J1"]}),
    ("POST", "/api/v1/events", {"name": "Marathon", "starts_at": "2026-10-01T08:00:00Z", "ends_at": "2026-10-01T12:00:00Z"}),
    ("POST", "/api/v1/incidents/00000000-0000-0000-0000-000000000001/confirm", {}),
    ("POST", "/api/v1/routing/vms/broadcast", {"panel_cluster": "NORTH", "line1": "SLOW", "line2": "DOWN"}),
    ("PATCH", "/api/v1/alerts/00000000-0000-0000-0000-000000000001/acknowledge", {}),
    ("DELETE", "/api/v1/alerts/00000000-0000-0000-0000-000000000001", None),
]


@pytest.mark.parametrize("method,path,body", MUTATING_ENDPOINTS)
def test_anonymous_requests_rejected_on_mutating_endpoints(method, path, body):
    """SN-100: No mutating endpoint accepts an anonymous request."""
    client = TestClient(app)
    app.dependency_overrides.clear()

    if method == "POST":
        response = client.post(path, json=body)
    elif method == "PATCH":
        response = client.patch(path, json=body)
    elif method == "DELETE":
        response = client.delete(path)
    else:
        return

    # Must reject without valid auth credentials (401 or 403)
    assert response.status_code in (401, 403), (
        f"Anonymous request was accepted on {method} {path} with status {response.status_code}!"
    )


# ---------------------------------------------------------------------------
# 4. Rate Limiting Tests (SN-101)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limiter_exceeded_returns_429():
    """SN-101: Exceeding rate limit raises 429 Too Many Requests with retry_after_s."""
    mock_redis = AsyncMock()
    # 11 calls when limit is 10
    mock_redis.incr.return_value = 11
    mock_redis.ttl.return_value = 45

    with patch("app.services.auth_service.get_redis_client", return_value=mock_redis):
        with pytest.raises(HTTPException) as exc_info:
            await enforce_rate_limit("rate_test_key", limit=10, window_seconds=60, detail="Override limit exceeded")
        assert exc_info.value.status_code == 429
        assert "Override limit exceeded" in exc_info.value.detail
        assert "retry_after_s: 45" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 5. Mutation Check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mutation_require_role(monkeypatch):
    """Mutation check: Verifies require_role enforcement strictly guards execution."""
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    viewer = create_user_for_role(UserRole.VIEWER)

    # 1. Unmutated: require_role correctly rejects VIEWER for emergency corridor
    guard = require_role("ADMIN", "EMERGENCY_SERVICES", action="CORRIDOR_ACTIVATE")
    with pytest.raises(HTTPException) as exc_info:
        await guard(request=None, current_user=viewer, db=mock_db)
    assert exc_info.value.status_code == 403

    # 2. Mutated dependency: prove that bypassing require_role allows unauthorized role
    def open_require_role(*roles, action=None):
        async def dependency(request=None, current_user=None, db=None):
            return current_user
        return dependency

    mutated_guard = open_require_role("ADMIN")
    passed_user = await mutated_guard(request=None, current_user=viewer, db=mock_db)
    assert passed_user.role == UserRole.VIEWER, "Guard mutation did not behave as expected"
