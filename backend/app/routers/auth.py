"""
Authentication Router — JWT-based auth for RapidAid.ai

Endpoints:
  POST /auth/register  — Create a new patient account
  POST /auth/login     — Login with phone + password → JWT token
  GET  /auth/me        — Get current user (requires valid token)

Token is Bearer JWT. Include in headers:
  Authorization: Bearer <token>
"""
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.database import AsyncSession, get_db
from app.models.db_models import User, UserRole

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


# ─────────────────────────── Pydantic Schemas ────────────────────────────

class RegisterRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=7, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    email: Optional[str] = Field(None, max_length=150)


class LoginRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    password: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user_id: str
    user_name: str
    role: str


class UserResponse(BaseModel):
    id: str
    name: str
    phone: str
    email: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────────────────────────── Helpers ─────────────────────────────────────

def _hash_password(password: str) -> str:
    """SHA-256 hash with app SECRET_KEY as salt. Simple, no deps on passlib."""
    salted = f"{settings.SECRET_KEY}:{password}"
    return hashlib.sha256(salted.encode()).hexdigest()


def _verify_password(plain: str, hashed: str) -> bool:
    return _hash_password(plain) == hashed


def _create_access_token(user_id: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _decode_token(token: str) -> dict:
    """Decode and validate JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ─────────────────────────── Dependencies ────────────────────────────────

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — validates Bearer token and returns the User ORM object."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = _decode_token(credentials.credentials)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    return user


def require_role(*roles: UserRole):
    """Dependency factory — enforces that current user has one of the given roles."""
    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return _check


# ─────────────────────────── Endpoints ───────────────────────────────────

@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new patient account. Returns JWT token on success."""
    # Check phone uniqueness
    existing = (await db.execute(select(User).where(User.phone == request.phone))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Phone number already registered")

    # Check email uniqueness if provided
    if request.email:
        existing_email = (await db.execute(select(User).where(User.email == request.email))).scalar_one_or_none()
        if existing_email:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=request.name,
        phone=request.phone,
        email=request.email,
        role=UserRole.PATIENT,
        hashed_password=_hash_password(request.password),
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = _create_access_token(user.id, user.role.value)
    logger.info("New patient registered: %s (%s)", user.name, user.phone)

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        user_name=user.name,
        role=user.role.value,
    )


@auth_router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login with phone + password.
    Demo accounts (hashed_password='demo1234') use plaintext check for hackathon convenience.
    Production: all new accounts use hashed passwords.
    """
    result = await db.execute(select(User).where(User.phone == request.phone))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid phone or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    # Support both demo plaintext passwords and properly hashed ones
    password_valid = (
        _verify_password(request.password, user.hashed_password)
        or user.hashed_password == request.password  # demo mode: plaintext
    )
    if not password_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid phone or password")

    token = _create_access_token(user.id, user.role.value)
    logger.info("User logged in: %s [%s]", user.name, user.role.value)

    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user_id=user.id,
        user_name=user.name,
        role=user.role.value,
    )


@auth_router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        phone=current_user.phone,
        email=current_user.email,
        role=current_user.role.value,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
