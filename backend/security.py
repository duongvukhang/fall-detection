"""
SafeWatch — Security Utilities
Password hashing (bcrypt), JWT bearer tokens, API-key extraction.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import User

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (pull from environment in production)
# ─────────────────────────────────────────────────────────────────────────────
SECRET_KEY      : str = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION_USE_openssl_rand_hex_32")
ALGORITHM       : str = "HS256"
ACCESS_TOKEN_TTL: int = int(os.getenv("JWT_TTL_MINUTES", 60 * 24))  # 24 h default

# ─────────────────────────────────────────────────────────────────────────────
# Password
# ─────────────────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ─────────────────────────────────────────────────────────────────────────────
# JWT
# ─────────────────────────────────────────────────────────────────────────────

def create_access_token(user_id: int, facility: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_TTL)
    payload = {
        "sub"      : str(user_id),
        "facility" : facility,
        "exp"      : expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except JWTError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI Dependencies
# ─────────────────────────────────────────────────────────────────────────────

_bearer_scheme    = HTTPBearer(auto_error=False)
_api_key_scheme   = APIKeyHeader(name="X-API-KEY", auto_error=False)

_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
_403 = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """JWT guard for dashboard / account routes."""
    if not credentials:
        raise _401
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _401
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise _401
    return user


async def get_facility_from_api_key(
    api_key: Optional[str] = Security(_api_key_scheme),
    db     : AsyncSession  = Depends(get_db),
) -> User:
    """
    Edge-device guard for the telemetry ingest endpoint.
    Reads the X-API-KEY header, matches it to a user row,
    and returns that User so the event can be scoped to the correct tenant.
    """
    if not api_key:
        raise _403
    result = await db.execute(select(User).where(User.api_token == api_key))
    user = result.scalar_one_or_none()
    if user is None:
        raise _403
    return user
