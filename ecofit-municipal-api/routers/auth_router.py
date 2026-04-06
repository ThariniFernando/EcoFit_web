import os
from datetime import datetime, timezone, timedelta

import anyio
import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import database

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

users_col = database["users"]

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(credentials.credentials)


async def _hash_password(password: str) -> str:
    return await anyio.to_thread.run_sync(
        lambda: bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    )


async def _verify_password(password: str, hashed: str) -> bool:
    return await anyio.to_thread.run_sync(
        lambda: bcrypt.checkpw(password.encode(), hashed.encode())
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.post("/sign-up")
async def sign_up(payload: dict):
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = await users_col.find_one({"email": email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.now(timezone.utc)
    password_hash = await _hash_password(password)

    doc = {
        "fullName": payload.get("fullName", ""),
        "role": payload.get("role", "Municipal Officer"),
        "email": email,
        "phone": payload.get("phone"),
        "organization": payload.get("organization"),
        "passwordHash": password_hash,
        "createdAt": now,
        "updatedAt": now,
    }

    result = await users_col.insert_one(doc)
    user_id = str(result.inserted_id)
    token = _make_token(user_id, email, doc["role"])

    return {
        "message": "Account created successfully",
        "id": user_id,
        "token": token,
    }


@router.post("/sign-in")
async def sign_in(payload: dict):
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    user = await users_col.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=401, detail="Login unsuccessful")

    if not await _verify_password(password, user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Login unsuccessful")

    user_id = str(user["_id"])
    role = user.get("role", "Municipal Officer")
    token = _make_token(user_id, email, role)

    return {
        "message": "Login successful",
        "token": token,
        "user": {
            "id": user_id,
            "fullName": user.get("fullName"),
            "email": user.get("email"),
            "role": role,
        },
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Verify token and return current user info."""
    return current_user