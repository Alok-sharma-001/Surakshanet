from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from jose import JWTError, jwt
import bcrypt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.models.user import User
from app.schemas.auth import UserCreate
from app.database import get_db
from app.config import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def revoke_token(jti: str, expires_in_seconds: int) -> None:
    if not jti:
        return
    ttl = max(int(expires_in_seconds), 1)
    try:
        redis = get_redis_client()
        await redis.setex(f"revoked_token:{jti}", ttl, "revoked")
    except Exception:
        pass


async def is_token_revoked(jti: str) -> bool:
    if not jti:
        return False
    try:
        redis = get_redis_client()
        res = await redis.get(f"revoked_token:{jti}")
        return bool(res)
    except Exception:
        return False


async def check_login_rate_limit(identifier: str) -> None:
    """Enforce account lockout after 5 consecutive failed login attempts."""
    if not identifier:
        return
    try:
        redis = get_redis_client()
        key = f"auth:failed_logins:{identifier.strip().lower()}"
        attempts = await redis.get(key)
        if attempts and int(attempts) >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Account temporarily locked for 15 minutes."
            )
    except HTTPException:
        raise
    except Exception:
        pass


async def record_login_failure(identifier: str) -> None:
    """Increment failed login attempts counter with 15-minute expiration."""
    if not identifier:
        return
    try:
        redis = get_redis_client()
        key = f"auth:failed_logins:{identifier.strip().lower()}"
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, 900)
        await pipe.execute()
    except Exception:
        pass


async def reset_login_failures(identifier: str) -> None:
    """Reset failed login counter upon successful authentication."""
    if not identifier:
        return
    try:
        redis = get_redis_client()
        key = f"auth:failed_logins:{identifier.strip().lower()}"
        await redis.delete(key)
    except Exception:
        pass


def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    if "jti" not in to_encode:
        to_encode["jti"] = str(uuid.uuid4())
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    if "jti" not in to_encode:
        to_encode["jti"] = str(uuid.uuid4())
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


async def get_optional_current_user(token: Optional[str] = Depends(oauth2_scheme_optional), db: AsyncSession = Depends(get_db)) -> Optional[User]:
    """Resolves current user if a valid token is provided, returns None gracefully if no token provided, or raises 401 if an invalid/revoked token was provided."""
    if not token:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"}
        )
    user_id_str: str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    user_id = UUID(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def enforce_rate_limit(
    key: str,
    limit: int,
    window_seconds: int = 60,
    detail: str = "Rate limit exceeded"
) -> None:
    """Generic Redis-backed rate limiter (SN-101).
    Raises 429 with retry_after_s when limit is exceeded.
    """
    try:
        redis = get_redis_client()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, window_seconds)

        if count > limit:
            ttl = await redis.ttl(key)
            retry_after = max(int(ttl), 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"{detail}. retry_after_s: {retry_after}",
                headers={"Retry-After": str(retry_after)},
            )
    except HTTPException:
        raise
    except Exception:
        # Best effort fail-open if Redis is unavailable
        pass


def _infer_action(request: Optional[Request]) -> str:
    if not request:
        return "OPERATION"
    path = request.url.path.lower()
    method = request.method.upper()
    if "/emergency/activate" in path:
        return "CORRIDOR_ACTIVATE"
    if "/emergency/deactivate" in path:
        return "CORRIDOR_DEACTIVATE"
    if "/signals/" in path and "/mode" in path:
        return "SIGNAL_MODE_CHANGE"
    if "/signals/" in path and "/override" in path:
        return "SIGNAL_OVERRIDE"
    if "/signals/" in path and "/decision" in path:
        return "SIGNAL_DECISION_READ"
    if "/incidents/" in path and "/confirm" in path:
        return "INCIDENT_CONFIRM"
    if "/incidents/" in path and "/dismiss" in path:
        return "INCIDENT_DISMISS"
    if "/incidents/" in path and "/escalate" in path:
        return "INCIDENT_ESCALATE"
    if "/incidents/" in path and "/publish-warning" in path:
        return "PUBLIC_WARNING_PUBLISH"
    if "/events/" in path and "/approve" in path:
        return "EVENT_APPROVE"
    if "/events/" in path and "/publish" in path:
        return "ADVISORY_PUBLISH"
    if "/events/" in path and "/predict" in path:
        return "EVENT_PREDICT"
    if "/routing/vms/broadcast" in path:
        return "ROUTE_DIVERSION"
    if "/ml/train" in path:
        return "ML_TRAIN"
    if "/ab/run" in path:
        return "AB_RUN"
    if "/audit" in path:
        return "AUDIT_READ"
    return f"{method}_{path.strip('/').replace('/', '_').upper()}"


def require_role(*roles: str, action: Optional[str] = None):
    """Dependency enforcing role check, logging ACCESS_DENIED audit row on 403 (SN-099, SN-100)."""
    async def role_checker(
        request: Request = None,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user_role = getattr(current_user.role, 'value', getattr(current_user.role, 'name', str(current_user.role)))
        if user_role not in roles:
            action_name = action or _infer_action(request)

            # Record ACCESS_DENIED audit row per SN-099 & SN-104
            if db is not None:
                try:
                    from app.services.audit_service import write_audit
                    from app.models.audit import AuditActorType, AuditResult
                    corr_id = None
                    path_str = ""
                    method_str = ""
                    if request:
                        corr_id = getattr(request.state, "request_id", None) or request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")
                        path_str = str(request.url.path)
                        method_str = request.method

                    await write_audit(
                        db=db,
                        action="ACCESS_DENIED",
                        actor_type=AuditActorType.USER,
                        actor_id=current_user.id,
                        target_type="endpoint",
                        input_payload={
                            "role": user_role,
                            "attempted_action": action_name,
                            "path": path_str,
                            "method": method_str,
                            "required_roles": list(roles),
                        },
                        result=AuditResult.DENIED,
                        source="rbac",
                        correlation_id=corr_id,
                    )
                    await db.commit()
                except Exception as e:
                    import logging
                    logging.getLogger("surakshanet.rbac").warning(f"Could not record ACCESS_DENIED audit log: {e}")

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role {user_role} cannot perform {action_name}"
            )
        return current_user
    return role_checker


async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    from app.models.user import UserRole
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = hash_password(user_data.password)
    # Invariant §13.4: registration always creates OPERATOR — a role field
    # on the request body (UserCreate.role) must never be trusted, or any
    # anonymous caller could self-register as ADMIN. Promotion to a higher
    # role is only ever a separate, explicit PATCH /users/{id}/role action
    # by an existing ADMIN.
    db_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
        role=UserRole.OPERATOR
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def seed_default_admin(db: AsyncSession) -> None:
    """Seed default administrator account if it does not exist."""
    from app.models.user import UserRole
    settings = get_settings()
    admin_email = settings.ADMIN_EMAIL
    admin_password = settings.ADMIN_PASSWORD

    # Check if any admin user already exists or if admin_email is already taken
    result = await db.execute(select(User).where((User.email == admin_email) | (User.role == UserRole.ADMIN)))
    existing_admin = result.scalars().first()
    if not existing_admin:
        hashed_password = hash_password(admin_password)
        admin_user = User(
            email=admin_email,
            password_hash=hashed_password,
            name="System Administrator",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        await db.commit()
