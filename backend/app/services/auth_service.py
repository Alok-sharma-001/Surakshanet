from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid
from jose import JWTError, jwt
import bcrypt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
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

def require_role(*roles: str):
    def role_checker(current_user: User = Depends(get_current_user)):
        user_role = getattr(current_user.role, 'value', getattr(current_user.role, 'name', str(current_user.role)))
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted"
            )
        return current_user
    return role_checker

async def register_user(db: AsyncSession, user_data: UserCreate) -> User:
    from app.models.user import UserRole
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = hash_password(user_data.password)
    role = UserRole.OPERATOR
    db_user = User(
        email=user_data.email,
        password_hash=hashed_password,
        name=user_data.name,
        role=role
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
