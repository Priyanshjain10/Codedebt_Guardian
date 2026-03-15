"""
CodeDebt Guardian — Authentication & Authorization
JWT tokens, password hashing, GitHub OAuth, RBAC.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import settings
from database import get_db
from models.db_models import (
    APIKeyModel,
    Organization,
    Subscription,
    Team,
    TeamMember,
    User,
)

security = HTTPBearer(auto_error=False)


# ── Schemas ──────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: Optional[str] = None
    created_at: str

    model_config = {"from_attributes": True}


class APIKeyCreate(BaseModel):
    label: str = "default"


class APIKeyResponse(BaseModel):
    id: str
    key_prefix: str
    label: str
    created_at: str

    model_config = {"from_attributes": True}


# ── Password Hashing ────────────────────────────────────────────────────


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


# ── JWT Token Management ────────────────────────────────────────────────


def create_access_token(user_id: str, org_id: str = "") -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "org": org_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── API Key Management ──────────────────────────────────────────────────


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key. Returns (full_key, prefix, hash)."""
    raw = secrets.token_urlsafe(32)
    full_key = f"cdg_live_{raw}"
    prefix = full_key[:16]
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, prefix, key_hash


async def verify_api_key(key: str, db: AsyncSession) -> Optional[APIKeyModel]:
    """Verify an API key and return the associated record."""
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    result = await db.execute(
        select(APIKeyModel).where(
            APIKeyModel.key_hash == key_hash,
            APIKeyModel.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key:
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.flush()
    return api_key


# ── FastAPI Dependencies ─────────────────────────────────────────────────


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Authenticate via JWT Bearer token OR API key.
    Returns the authenticated User object.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token = credentials.credentials

    # Try API key first
    if token.startswith("cdg_"):
        api_key = await verify_api_key(token, db)
        if not api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
        result = await db.execute(select(User).where(User.id == api_key.user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        return user

    # JWT token
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user, but returns None instead of 401 if unauthenticated."""
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_role(min_role: str = "member"):
    """Dependency factory: checks the user has at least `min_role` in the org."""
    role_order = {"viewer": 0, "member": 1, "admin": 2, "owner": 3}

    async def _check(
        user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        result = await db.execute(
            select(TeamMember)
            .where(TeamMember.user_id == user.id)
            .order_by(TeamMember.joined_at)
            .limit(1)
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(
                status_code=403, detail="No team membership found for this account"
            )
        user_level = role_order.get(membership.role, 0)
        required_level = role_order.get(min_role, 1)
        if user_level < required_level:
            raise HTTPException(
                status_code=403, detail=f"Requires '{min_role}' role or higher"
            )
        return user

    return _check


# ── Registration & Login Handlers ────────────────────────────────────────


async def register_user(
    req: RegisterRequest, db: AsyncSession
) -> tuple[User, Organization]:
    """Create a new user with a default organization."""
    # Check for existing email
    existing = await db.execute(select(User).where(User.email == req.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user
    user = User(
        email=req.email,
        password_hash=hash_password(req.password),
        name=req.name,
    )
    db.add(user)
    await db.flush()

    # Create default org
    slug = req.email.split("@")[0].lower().replace(".", "-")
    org = Organization(
        name=f"{req.name}'s Workspace",
        slug=f"{slug}-{str(user.id)[:8]}",
        billing_email=req.email,
    )
    db.add(org)
    await db.flush()

    # Create default team
    team = Team(org_id=org.id, name="Default", slug="default")
    db.add(team)
    await db.flush()

    # Add user as owner
    membership = TeamMember(team_id=team.id, user_id=user.id, role="owner")
    db.add(membership)

    # Create free subscription
    sub = Subscription(org_id=org.id, plan="free", scans_limit_monthly=5)
    db.add(sub)

    await db.flush()
    return user, org


async def login_user(req: LoginRequest, db: AsyncSession) -> tuple[User, str]:
    """Verify credentials and return user + org_id."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Get primary org
    result = await db.execute(
        select(TeamMember)
        .options(selectinload(TeamMember.team))
        .where(TeamMember.user_id == user.id)
        .limit(1)
    )
    membership = result.scalar_one_or_none()
    org_id = str(membership.team.org_id) if membership else ""

    return user, org_id
