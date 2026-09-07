from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Any, Optional
from uuid import UUID

from app.database import get_db
from app.models.user import User
from app.schemas.auth import UserCreate, UserResponse, TokenResponse, UserUpdate
from app.services.auth_service import (
    register_user, 
    authenticate_user, 
    create_access_token, 
    create_refresh_token,
    get_current_user,
    decode_token,
    oauth2_scheme,
    revoke_token,
    is_token_revoked,
    check_login_rate_limit,
    record_login_failure,
    reset_login_failures
)

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)) -> Any:
    return await register_user(db, user_data)

@router.post("/login")
async def login(request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> Any:
    email = None
    password = None
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        try:
            body = await request.json()
            email = body.get("email") or body.get("username")
            password = body.get("password")
        except Exception:
            pass
    elif "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        email = form.get("username") or form.get("email")
        password = form.get("password")
    else:
        try:
            body = await request.json()
            email = body.get("email") or body.get("username")
            password = body.get("password")
        except Exception:
            try:
                form = await request.form()
                email = form.get("username") or form.get("email")
                password = form.get("password")
            except Exception:
                pass

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email/username and password are required",
        )

    await check_login_rate_limit(str(email))

    user = await authenticate_user(db, str(email), str(password))
    if not user:
        await record_login_failure(str(email))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    await reset_login_failures(str(email))
        
    role_str = getattr(user.role, 'value', getattr(user.role, 'name', str(user.role)))
    access_token = create_access_token(data={"sub": str(user.id), "role": role_str})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Secure httpOnly cookie for refresh token
    from app.config import get_settings
    auth_settings = get_settings()
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=auth_settings.ENVIRONMENT.lower() == "production",
        samesite="lax",
        max_age=auth_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/v1/auth",
    )

    user_data = {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": role_str,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None
    }
    
    return {
        "access_token": access_token,
        "token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user_data
    }

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
) -> Any:
    token_candidate = refresh_token or request.cookies.get("refresh_token")
    if not token_candidate:
        try:
            body = await request.json()
            token_candidate = body.get("refresh_token")
        except Exception:
            pass

    if not token_candidate:
        raise HTTPException(status_code=401, detail="Refresh token required")

    try:
        payload = decode_token(token_candidate)
        jti = payload.get("jti")
        if jti and await is_token_revoked(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=401, detail="Invalid token")
            
        user_id = UUID(user_id_str)
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
            
        role_str = getattr(user.role, 'value', getattr(user.role, 'name', str(user.role)))
        access_token = create_access_token(data={"sub": str(user.id), "role": role_str})
        new_refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
        from app.config import get_settings
        auth_settings = get_settings()
        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=auth_settings.ENVIRONMENT.lower() == "production",
            samesite="lax",
            max_age=auth_settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            path="/api/v1/auth",
        )

        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
) -> Any:
    """Revoke active JWT tokens, clear httpOnly cookie, and invalidate session."""
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            now_ts = datetime.now(timezone.utc).timestamp()
            remaining_ttl = int(exp - now_ts)
            if remaining_ttl > 0:
                await revoke_token(jti, remaining_ttl)
    except Exception:
        pass

    # Revoke refresh token from cookie or body if present
    refresh_token_val = request.cookies.get("refresh_token")
    if not refresh_token_val:
        try:
            body = await request.json()
            refresh_token_val = body.get("refresh_token")
        except Exception:
            pass

    if refresh_token_val:
        try:
            r_payload = decode_token(refresh_token_val)
            r_jti = r_payload.get("jti")
            r_exp = r_payload.get("exp")
            if r_jti and r_exp:
                r_ttl = int(r_exp - datetime.now(timezone.utc).timestamp())
                if r_ttl > 0:
                    await revoke_token(r_jti, r_ttl)
        except Exception:
            pass

    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"message": "Successfully logged out", "status": "logged_out"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)) -> Any:
    return current_user

@router.patch("/me", response_model=UserResponse)
async def update_me(
    user_update: UserUpdate, 
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
) -> Any:
    if user_update.name is not None:
        current_user.name = user_update.name
    
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user
