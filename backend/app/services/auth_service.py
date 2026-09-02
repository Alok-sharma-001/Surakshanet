from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.models.user import User
from app.schemas.auth import UserCreate
from app.database import get_db
from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
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
    admin_email = "aloks92440@gmail.com"
    result = await db.execute(select(User).where(User.email == admin_email))
    admin_user = result.scalar_one_or_none()
    if not admin_user:
        hashed_password = hash_password("Alok@2005")
        admin_user = User(
            email=admin_email,
            password_hash=hashed_password,
            name="Alok Sharma",
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin_user)
        await db.commit()
    elif not verify_password("Alok@2005", admin_user.password_hash):
        admin_user.password_hash = hash_password("Alok@2005")
        admin_user.role = UserRole.ADMIN
        admin_user.is_active = True
        db.add(admin_user)
        await db.commit()
