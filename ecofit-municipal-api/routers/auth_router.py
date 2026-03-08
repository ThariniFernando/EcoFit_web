from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from database import database
import bcrypt

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

users_col = database["users"]


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


@router.post("/sign-up")
async def sign_up(payload: dict):
    print("✅ sign-up called")

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    print("✅ checking existing user")
    existing = await users_col.find_one({"email": email})

    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    now = datetime.now(timezone.utc)

    print("✅ hashing password")
    password_hash = hash_password(password)

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

    print("✅ inserting user")
    result = await users_col.insert_one(doc)

    print("✅ sign-up success")
    return {
        "message": "Account created successfully",
        "id": str(result.inserted_id),
    }


@router.post("/sign-in")
async def sign_in(payload: dict):
    print("✅ sign-in called")

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", "")).strip()

    print("✅ finding user")
    user = await users_col.find_one({"email": email})

    if not user:
        raise HTTPException(status_code=401, detail="Login unsuccessful")

    print("✅ verifying password")
    if not verify_password(password, user.get("passwordHash", "")):
        raise HTTPException(status_code=401, detail="Login unsuccessful")

    print("✅ sign-in success")
    return {
        "message": "Login successful",
        "user": {
            "id": str(user["_id"]),
            "fullName": user.get("fullName"),
            "email": user.get("email"),
            "role": user.get("role"),
        },
    }